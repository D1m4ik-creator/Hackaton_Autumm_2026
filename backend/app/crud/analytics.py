from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.risk_summary import RiskSummaryDAO
from app.db.schemas.analytics import SummaryOut
from app.db.schemas.common import LEVELS, level_bucket


async def get_summary(session: AsyncSession) -> SummaryOut:
    """Сводка по всем клиентам из единственной строки risk_summary"""
    summary = await RiskSummaryDAO.get(session)
    by_level = (summary.by_level if summary else None) or {}
    return SummaryOut(
        customers_total=summary.customers_total if summary else 0,
        by_level={key: level_bucket(by_level, key) for key in LEVELS},
        expected_loss_cents=summary.expected_loss_cents if summary else 0,
        loss_explanation=summary.loss_explanation if summary else "",
        as_of=summary.as_of if summary else None,
        recalculated_at=summary.recalculated_at if summary else None,
        version=summary.version if summary else 0,
    )
