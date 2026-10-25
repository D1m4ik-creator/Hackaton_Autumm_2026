from collections.abc import Sequence

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

import app.crud.analytics as crud_analytics
import app.dao.customer_query as customer_query
from app.dao.account import AccountDAO
from app.dao.risk_result import RiskResultDAO
from app.dao.risk_summary import RiskSummaryDAO
from app.db.schemas.analytics import SummaryOut
from app.db.schemas.customers import CustomerService, CustomerTransactions
from app.db.schemas.public_report import PublicCustomerCard, PublicCustomerItem, PublicCustomerPage


async def get_summary(session: AsyncSession) -> SummaryOut:
    """Публичная сводка — тот же builder, что и у авторизованного /analytics/summary (email там и так нет)"""
    return await crud_analytics.get_summary(session)


async def list_customers(
    session: AsyncSession,
    *,
    levels: Sequence[str] | None,
    search: str | None,
    sort: str,
    order: str,
    page: int,
    page_size: int,
) -> PublicCustomerPage:
    """Та же выборка, что и у авторизованного списка клиентов, без email в ответе"""
    rows = await customer_query.query_customers(
        session, levels=levels, search=search, sort=sort, order=order, page=page, page_size=page_size
    )
    total = await customer_query.count_customers(session, levels=levels, search=search)
    items = [
        PublicCustomerItem(
            id=row.id,
            balance=row.balance,
            total_replenished=row.total_replenished,
            risk_score=row.score,
            level=row.level,
            expected_loss_cents=row.expected_loss_cents,
            reason_short=row.reason_short,
        )
        for row in rows
    ]
    return PublicCustomerPage(items=items, total=total, page=page, page_size=page_size)


async def get_customer_card(session: AsyncSession, customer_id: int) -> PublicCustomerCard:
    """Карточка клиента без email; 404, если клиента нет"""
    account = await AccountDAO.find_by_id(session, customer_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Клиент не найден")

    risk = await RiskResultDAO.get(session, customer_id)
    summary = await RiskSummaryDAO.get(session)
    services = await customer_query.customer_services(session, customer_id)
    tx = await customer_query.customer_transaction_counts(session, customer_id)

    return PublicCustomerCard(
        id=account.id,
        balance=account.balance,
        withdraw_balance=account.withdraw_balance,
        total_replenished=account.total_replenished,
        bonus_balance=account.bonus_balance,
        bonus_state=account.bonus_state,
        risk_score=risk.score if risk else None,
        level=risk.level if risk else "no_data",
        expected_loss_cents=risk.expected_loss_cents if risk else 0,
        reason_short=risk.reason_short if risk else "",
        reasons=risk.reasons if risk else [],
        details=risk.details if risk else {},
        services=[CustomerService.model_validate(svc) for svc in services],
        transactions=CustomerTransactions(
            total=tx["total"], performed=tx["performed"], not_performed=tx["not_performed"]
        ),
        as_of=summary.as_of if summary else None,
        calculated_at=risk.calculated_at if risk else None,
    )
