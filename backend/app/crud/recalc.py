"""Пересчёт риска: сбор снимка, вызов модели, материализация результатов (§6).

Все записи идут под advisory-блокировкой в текущей транзакции; lock снимается
на commit/rollback вызывающего. Формул модели здесь нет — только её вызов.
"""

import asyncio
import logging
from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import Row, text
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
    ensure_snapshot_valid,
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


class AnalysisContractError(Exception):
    """Модель вернула результат, нарушающий контракт (§5)"""


async def acquire_lock(session: AsyncSession) -> None:
    """Берёт транзакционную advisory-блокировку; снимается на commit/rollback"""
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:key)"), {"key": RECALC_LOCK_KEY}
    )


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
    stored = await ModelSettingsDAO.get(session)
    merged = deep_merge(analysis.default_settings(), stored)
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


async def recalculate(session: AsyncSession, reason: str) -> RiskSummary:
    """Полный пересчёт в текущей транзакции (§6.3); lock и commit — у вызывающего"""
    settings = await effective_settings(session)
    as_of = _resolve_as_of(settings)

    accounts = await AccountDAO.load_rows(session)
    services = await ServiceDAO.load_rows(session)
    transactions = await TransactionDAO.load_rows(session)
    source = _build_source(accounts, services, transactions)

    result = await asyncio.to_thread(analysis.analyze, source, settings, as_of)
    account_ids = {account.id for account in source.accounts}
    customers = check_result(result, account_ids)

    now = datetime.now(timezone.utc)
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

    await RiskResultDAO.replace_all(session, rows)
    return await RiskSummaryDAO.save(
        session,
        reason=reason,
        customers_total=len(customers),
        by_level=by_level,
        expected_loss_cents=total_loss,
        loss_explanation=result.loss_explanation,
        as_of=as_of,
        recalculated_at=now,
    )


async def apply_snapshot(session: AsyncSession, snapshot: SnapshotIn) -> SnapshotLoadResult:
    """Замена снимка и пересчёт одной транзакцией под блокировкой (§6.2)"""
    ensure_snapshot_valid(snapshot)
    await acquire_lock(session)
    counts = await replace_source_data(session, snapshot)
    summary = await recalculate(session, "snapshot")
    await session.commit()
    return SnapshotLoadResult(
        accounts=counts.accounts,
        services=counts.services,
        transactions=counts.transactions,
        version=summary.version,
        recalculated_at=summary.recalculated_at,
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

    await recalculate(session, "startup")
    await session.commit()
