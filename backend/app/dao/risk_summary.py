from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.base import BaseDAO
from app.db.models.risk_summary import RiskSummary


class RiskSummaryDAO(BaseDAO):
    model = RiskSummary

    @classmethod
    async def get(cls, session: AsyncSession) -> RiskSummary | None:
        """Строка сводки (id=1)"""
        return await session.get(RiskSummary, 1)

    @classmethod
    async def save(cls, session: AsyncSession, **values) -> RiskSummary:
        """Обновляет сводку, увеличивает version на 1, возвращает свежую строку; без commit"""
        await session.execute(
            update(RiskSummary)
            .where(RiskSummary.id == 1)
            .values(version=RiskSummary.version + 1, **values)
        )
        summary = await session.get(RiskSummary, 1)
        await session.refresh(summary)
        return summary
