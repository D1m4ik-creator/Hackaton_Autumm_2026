import json
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.account import AccountDAO
from app.dao.risk_result import RiskResultDAO
from app.dao.service import ServiceDAO
from app.dao.transaction import TransactionDAO
from app.db.schemas.source import SnapshotIn

# Максимум пунктов в ответе 422, чтобы не раздувать тело ошибки
MAX_ERRORS = 50


@dataclass(frozen=True)
class SourceCounts:
    """Сколько строк каждой сущности загружено"""

    accounts: int
    services: int
    transactions: int


def ensure_snapshot_valid(snapshot: SnapshotIn) -> None:
    """Проверки между записями снимка; при нарушениях — HTTPException(422) в формате FastAPI"""
    errors: list[dict] = []

    def add(loc: list, msg: str, typ: str) -> None:
        if len(errors) < MAX_ERRORS:
            errors.append({"loc": loc, "msg": msg, "type": typ})

    # accounts: повторы id и email
    account_ids: set[int] = set()
    seen_ids: set[int] = set()
    email_first: dict[str, int] = {}
    for i, acc in enumerate(snapshot.accounts):
        if acc.id in seen_ids:
            add(["body", "accounts", i, "id"], f"Повторяется id={acc.id}", "duplicate_id")
        else:
            seen_ids.add(acc.id)
            account_ids.add(acc.id)
        if acc.email in email_first:
            owner_id = snapshot.accounts[email_first[acc.email]].id
            add(
                ["body", "accounts", i, "email"],
                f"Email уже есть у аккаунта id={owner_id}",
                "duplicate_email",
            )
        else:
            email_first[acc.email] = i

    # services: повторы id и ссылка на существующий аккаунт
    service_ids: set[int] = set()
    seen_service_ids: set[int] = set()
    for i, svc in enumerate(snapshot.services):
        if svc.id in seen_service_ids:
            add(["body", "services", i, "id"], f"Повторяется id={svc.id}", "duplicate_id")
        else:
            seen_service_ids.add(svc.id)
            service_ids.add(svc.id)
        if svc.owner_id not in account_ids:
            add(
                ["body", "services", i, "ownerId"],
                f"Аккаунт ownerId={svc.owner_id} не найден",
                "reference_not_found",
            )

    # transactions: повторы id, ссылка на услугу, согласованность статуса и performedAt
    seen_tx_ids: set[int] = set()
    for i, tx in enumerate(snapshot.transactions):
        if tx.id in seen_tx_ids:
            add(["body", "transactions", i, "id"], f"Повторяется id={tx.id}", "duplicate_id")
        else:
            seen_tx_ids.add(tx.id)
        if tx.service_id not in service_ids:
            add(
                ["body", "transactions", i, "serviceId"],
                f"Услуга serviceId={tx.service_id} не найдена",
                "reference_not_found",
            )
        if tx.status == "performed" and tx.performed_at is None:
            add(
                ["body", "transactions", i, "performedAt"],
                "Транзакция со статусом performed должна иметь performedAt",
                "value_error",
            )
        if tx.status == "not_performed" and tx.performed_at is not None:
            add(
                ["body", "transactions", i, "performedAt"],
                "Транзакция со статусом not_performed не должна иметь performedAt",
                "value_error",
            )

    if errors:
        raise HTTPException(status_code=422, detail=errors)


async def replace_source_data(session: AsyncSession, snapshot: SnapshotIn) -> SourceCounts:
    """Полная замена исходных данных без commit. DELETE (не TRUNCATE): читатели до commit видят старое."""
    await RiskResultDAO.delete_all(session)
    await TransactionDAO.delete_all(session)
    await ServiceDAO.delete_all(session)
    await AccountDAO.delete_all(session)

    await AccountDAO.bulk_insert(session, [a.model_dump(by_alias=False) for a in snapshot.accounts])
    await ServiceDAO.bulk_insert(session, [s.model_dump(by_alias=False) for s in snapshot.services])
    await TransactionDAO.bulk_insert(
        session, [t.model_dump(by_alias=False) for t in snapshot.transactions]
    )

    return SourceCounts(
        accounts=len(snapshot.accounts),
        services=len(snapshot.services),
        transactions=len(snapshot.transactions),
    )


def read_snapshot_file(path: Path) -> SnapshotIn | None:
    """Читает снимок из файла: нет файла -> None; есть, но невалиден -> ValueError"""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return SnapshotIn.model_validate(data)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"Файл снимка повреждён: {exc}") from exc
