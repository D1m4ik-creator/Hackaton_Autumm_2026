"""Пересчёт риска: сбор снимка, вызов модели, материализация результатов (§6).

Все записи идут под advisory-блокировкой в текущей транзакции; lock снимается
на commit/rollback вызывающего. Формул модели здесь нет — только её вызов.
"""

import asyncio
import json
import logging
from collections.abc import Sequence
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import Row, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app import analysis
from app.analysis.types import (
    AccountData,
    AnalysisResult,
    CustomerRisk,
    Reason,
    ServiceData,
    SourceData,
    TransactionData,
)
from app.core.config import get_settings
from app.crud.source import (
    ensure_merge_valid,
    ensure_snapshot_valid,
    merge_source_data,
    read_snapshot_file,
    replace_source_data,
)
from app.dao.account import AccountDAO
from app.dao.model_settings import ModelSettingsDAO
from app.dao.risk_result import RiskResultDAO
from app.dao.risk_summary import RiskSummaryDAO
from app.dao.service import ServiceDAO
from app.dao.transaction import TransactionDAO
from app.db.models.risk_summary import RiskSummary
from app.db.schemas.common import LEVELS
from app.db.schemas.source import SnapshotIn, SnapshotLoadResult

logger = logging.getLogger(__name__)

# Ключ advisory-блокировки пересчёта (общий для всех воркеров)
RECALC_LOCK_KEY = 815_007_001

# Сколько ждать advisory-блокировку, прежде чем отдать 503 (мс)
LOCK_TIMEOUT_MS = 15_000
# Сколько секунд советуем подождать до повтора запроса
LOCK_RETRY_AFTER_SECONDS = 5
# SQLSTATE, который Postgres возвращает при срабатывании lock_timeout
_LOCK_NOT_AVAILABLE_SQLSTATE = "55P03"


class AnalysisContractError(Exception):
    """Модель вернула результат, нарушающий контракт (§5)"""


def _is_lock_timeout(exc: DBAPIError) -> bool:
    """True, если ошибка — срабатывание lock_timeout (55P03)"""
    return getattr(getattr(exc, "orig", None), "sqlstate", None) == _LOCK_NOT_AVAILABLE_SQLSTATE


async def acquire_lock(session: AsyncSession) -> None:
    """Берёт транзакционную advisory-блокировку; снимается на commit/rollback.

    Ожидание ограничено lock_timeout: если блокировку удерживает другой пересчёт
    дольше LOCK_TIMEOUT_MS, вместо бесконечного ожидания возвращаем 503.
    """
    # SET LOCAL действует до конца транзакции; этот же execute её и открывает
    await session.execute(
        text("SELECT set_config('lock_timeout', :ms, true)"), {"ms": str(LOCK_TIMEOUT_MS)}
    )
    try:
        await session.execute(
            text("SELECT pg_advisory_xact_lock(:key)"), {"key": RECALC_LOCK_KEY}
        )
    except DBAPIError as exc:
        if _is_lock_timeout(exc):
            await session.rollback()
            raise HTTPException(
                status_code=503,
                detail="Идёт пересчёт данных, повторите запрос позже",
                headers={"Retry-After": str(LOCK_RETRY_AFTER_SECONDS)},
            ) from exc
        raise


# Ключ в сохранённых настройках: список удалённых пунктов вида «секция.ключ».
# Нужен, потому что эффективные настройки = дефолты + сохранённое, и без него дефолтный пункт возвращался бы после удаления
REMOVED_KEY = "_removed"


def split_stored(stored: dict) -> tuple[dict, list[str]]:
    """Делит сохранённые настройки на сами настройки и список удалённых пунктов"""
    data = dict(stored)
    removed = [p for p in data.pop(REMOVED_KEY, []) if isinstance(p, str)]
    return data, removed


def apply_removals(settings: dict, removed: list[str]) -> dict:
    """Убирает из настроек удалённые пункты «секция.ключ» (если секции или ключа уже нет, ничего не делает)"""
    for path in removed:
        section, _, key = path.partition(".")
        if isinstance(settings.get(section), dict):
            settings[section] = {k: v for k, v in settings[section].items() if k != key}
    return settings


def deep_merge(base: dict, override: dict) -> dict:
    """Рекурсивно сливает словари; не-словарные значения заменяются целиком (§6.2)"""
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


async def effective_settings(session: AsyncSession) -> dict:
    """Эффективные настройки: deep-merge дефолтов и сохранённого, прошедший валидацию.

    Если сохранённое после обновления модели не проходит validate_settings —
    предупреждение в лог и возврат к дефолтам (строка в БД не трогается).
    """
    data, removed = split_stored(await ModelSettingsDAO.get(session))
    merged = apply_removals(deep_merge(analysis.default_settings(), data), removed)
    try:
        return analysis.validate_settings(merged)
    except ValueError as exc:
        logger.warning("Сохранённые настройки невалидны, использую дефолтные: %s", exc)
        return analysis.validate_settings(analysis.default_settings())


def _resolve_as_of(settings: dict) -> datetime:
    """as_of из настроек (ключ asOf, ISO-8601) либо текущий момент UTC (§5)"""
    raw = settings.get("asOf")
    if isinstance(raw, str) and raw:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    return datetime.now(timezone.utc)


def _build_source(
    accounts: Sequence[Row], services: Sequence[Row], transactions: Sequence[Row]
) -> SourceData:
    """Собирает SourceData из строк БД (без N+1)"""
    return SourceData(
        accounts=[
            AccountData(
                id=r.id,
                email=r.email,
                balance=r.balance,
                withdraw_balance=r.withdraw_balance,
                total_replenished=r.total_replenished,
                bonus_balance=r.bonus_balance,
                bonus_state=r.bonus_state,
            )
            for r in accounts
        ],
        services=[
            ServiceData(
                id=r.id,
                name=r.name,
                owner_id=r.owner_id,
                payment_term=r.payment_term,
                auto_prolong=r.auto_prolong,
                created_at=r.created_at,
                expires_at=r.expires_at,
                status=r.status,
                price=r.price,
            )
            for r in services
        ],
        transactions=[
            TransactionData(
                id=r.id,
                amount=r.amount,
                status=r.status,
                performed_at=r.performed_at,
                created_at=r.created_at,
                type=r.type,
                service_id=r.service_id,
            )
            for r in transactions
        ],
    )


def _is_int(value: object) -> bool:
    """int, но не bool"""
    return isinstance(value, int) and not isinstance(value, bool)


def check_result(result: AnalysisResult, account_ids: set[int]) -> list[CustomerRisk]:
    """Проверяет результат модели по контракту (§5); дополняет пропущенных клиентов.

    Нарушение контракта -> AnalysisContractError. Клиент без результата получает
    level="no_data" с причиной «Модель не вернула оценку».
    """
    seen: set[int] = set()
    checked: list[CustomerRisk] = []
    for customer in result.customers:
        account_id = customer.account_id
        if account_id not in account_ids:
            raise AnalysisContractError(f"account_id={account_id} отсутствует в снимке")
        if account_id in seen:
            raise AnalysisContractError(f"account_id={account_id} повторяется в результате")
        seen.add(account_id)

        if customer.level not in LEVELS:
            raise AnalysisContractError(
                f"account_id={account_id}: недопустимый level={customer.level!r}"
            )
        if customer.score is None:
            if customer.level != "no_data":
                raise AnalysisContractError(
                    f"account_id={account_id}: score=None допустим только при level='no_data'"
                )
        else:
            if not _is_int(customer.score) or not (0 <= customer.score <= 100):
                raise AnalysisContractError(
                    f"account_id={account_id}: score должен быть int 0..100"
                )
            if customer.level == "no_data":
                raise AnalysisContractError(
                    f"account_id={account_id}: level='no_data' требует score=None"
                )
        if not isinstance(customer.reasons, list) or not all(
            isinstance(r, Reason) and isinstance(r.code, str) and isinstance(r.text, str) for r in customer.reasons
        ):
            raise AnalysisContractError(f"account_id={account_id}: reasons должен быть списком Reason(code, text)")
        if not isinstance(customer.details, dict):
            raise AnalysisContractError(f"account_id={account_id}: details должен быть dict")
        try:
            json.dumps(customer.details, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise AnalysisContractError(f"account_id={account_id}: details не сериализуется в JSON: {exc}") from exc
        if not _is_int(customer.expected_loss_cents) or customer.expected_loss_cents < 0:
            raise AnalysisContractError(
                f"account_id={account_id}: expected_loss_cents должен быть int >= 0"
            )
        checked.append(customer)

    for account_id in account_ids - seen:
        checked.append(
            CustomerRisk(
                account_id=account_id,
                score=None,
                level="no_data",
                reasons=[Reason("no_result", "Модель не вернула оценку")],
                expected_loss_cents=0,
                details={},
            )
        )
    return checked


def _materialize(result: AnalysisResult, account_ids: set[int], now: datetime) -> tuple[list[dict], dict, int, int]:
    """Чистая CPU-часть пересчёта: проверка контракта, строки результатов и агрегаты.

    Вынесена в отдельную функцию, чтобы считать её в потоке (asyncio.to_thread) и
    не блокировать цикл событий на больших снимках (100k+ клиентов).
    """
    customers = check_result(result, account_ids)
    by_level = {level: {"customers": 0, "expectedLossCents": 0} for level in LEVELS}
    total_loss = 0
    rows: list[dict] = []
    for customer in customers:
        reasons = [{"code": reason_.code, "text": reason_.text} for reason_ in customer.reasons]
        reason_short = customer.reasons[0].text if customer.reasons else ""
        rows.append(
            {
                "account_id": customer.account_id,
                "score": customer.score,
                "level": customer.level,
                "reason_short": reason_short,
                "reasons": reasons,
                "expected_loss_cents": customer.expected_loss_cents,
                "details": customer.details,
                "calculated_at": now,
            }
        )
        by_level[customer.level]["customers"] += 1
        by_level[customer.level]["expectedLossCents"] += customer.expected_loss_cents
        total_loss += customer.expected_loss_cents
    return rows, by_level, total_loss, len(customers)


async def recalculate(session: AsyncSession, reason: str) -> RiskSummary:
    """Полный пересчёт в текущей транзакции (§6.3); lock и commit — у вызывающего"""
    settings = await effective_settings(session)
    as_of = _resolve_as_of(settings)

    accounts = await AccountDAO.load_rows(session)
    services = await ServiceDAO.load_rows(session)
    transactions = await TransactionDAO.load_rows(session)
    # Сборка снимка из строк БД — чистый CPU, считаем в потоке
    source = await asyncio.to_thread(_build_source, accounts, services, transactions)

    try:
        result = await asyncio.to_thread(analysis.analyze, source, settings, as_of)
    except AnalysisContractError:
        raise
    except Exception as exc:
        logger.exception("Модель анализа завершилась с ошибкой")
        raise AnalysisContractError(f"модель завершилась с ошибкой: {exc}") from exc
    if not isinstance(result.customers, list) or not isinstance(result.loss_explanation, str):
        raise AnalysisContractError("результат модели должен содержать customers (list) и loss_explanation (str)")
    account_ids = {account.id for account in source.accounts}

    now = datetime.now(timezone.utc)
    # Проверка контракта и сборка строк/агрегатов — тоже CPU, в потоке
    rows, by_level, total_loss, customers_total = await asyncio.to_thread(
        _materialize, result, account_ids, now
    )

    await RiskResultDAO.replace_all(session, rows)
    return await RiskSummaryDAO.save(
        session,
        reason=reason,
        customers_total=customers_total,
        by_level=by_level,
        expected_loss_cents=total_loss,
        loss_explanation=result.loss_explanation,
        as_of=as_of,
        recalculated_at=now,
    )


async def apply_snapshot(
    session: AsyncSession, snapshot: SnapshotIn, mode: str = "replace"
) -> SnapshotLoadResult:
    """Загрузка снимка и пересчёт одной транзакцией под блокировкой (§6.2).

    mode="replace" (по умолчанию) — полная замена, как раньше. mode="merge" —
    добавление к существующим данным; DB-aware проверки (ensure_merge_valid)
    обязаны идти после acquire_lock — иначе два параллельных merge могли бы
    оба пройти проверку по данным до коммита друг друга (race на дубликаты id).
    """
    ensure_snapshot_valid(snapshot, mode)
    await acquire_lock(session)
    if mode == "merge":
        await ensure_merge_valid(session, snapshot)
        counts = await merge_source_data(session, snapshot)
    else:
        counts = await replace_source_data(session, snapshot)
    summary = await recalculate(session, "snapshot")
    await session.commit()
    return SnapshotLoadResult(
        accounts=counts.accounts,
        services=counts.services,
        transactions=counts.transactions,
        version=summary.version,
        recalculated_at=summary.recalculated_at,
        mode=mode,
    )


async def startup(session: AsyncSession) -> None:
    """Старт: блокировка -> первичная загрузка в пустую базу -> пересчёт -> commit (§6.4)"""
    settings = get_settings()
    await acquire_lock(session)

    snapshot: SnapshotIn | None = None
    if settings.seed_on_startup and await AccountDAO.count(session) == 0:
        try:
            snapshot = read_snapshot_file(settings.source_data_path)
            if snapshot is None:
                logger.warning(
                    "Файл снимка %s не найден, старт с пустой базой", settings.source_data_path
                )
            else:
                ensure_snapshot_valid(snapshot)
        except Exception as exc:  # noqa: BLE001 — любой сбой загрузки не должен ронять старт
            logger.warning("Снимок не загружен, старт с пустой базой: %s", exc)
            snapshot = None
        if snapshot is not None:
            await replace_source_data(session, snapshot)
            # Посев фиксируется сразу: сбой пересчёта (например, в модели) не должен его откатывать
            await session.commit()
            await acquire_lock(session)

    try:
        await recalculate(session, "startup")
        await session.commit()
    except Exception:
        await session.rollback()
        logger.exception("Пересчёт при старте не удался, данные загружены без оценок")
