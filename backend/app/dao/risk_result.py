from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.base import BaseDAO
from app.db.models.risk_result import RiskResult


class RiskResultDAO(BaseDAO):
    model = RiskResult

    @classmethod
    async def replace_all(cls, session: AsyncSession, rows: list[dict]) -> None:
        """Полностью заменяет результаты: DELETE всех строк + пакетная вставка, без commit"""
        await cls.delete_all(session)
        await cls.bulk_insert(session, rows)

    @classmethod
    async def get(cls, session: AsyncSession, account_id: int) -> RiskResult | None:
        """Результат по клиенту или None"""
        return await session.get(RiskResult, account_id)
