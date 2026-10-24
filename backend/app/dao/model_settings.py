from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.base import BaseDAO
from app.db.models.model_settings import ModelSettings


class ModelSettingsDAO(BaseDAO):
    model = ModelSettings

    @classmethod
    async def get(cls, session: AsyncSession) -> dict:
        """Сохранённые настройки (только сохранённое, без дефолтов); {} если пусто"""
        result = await session.execute(select(ModelSettings.data).where(ModelSettings.id == 1))
        data = result.scalar_one_or_none()
        return data or {}

    @classmethod
    async def save(cls, session: AsyncSession, data: dict) -> None:
        """Сохраняет настройки в строку id=1 без commit"""
        await session.execute(
            update(ModelSettings)
            .where(ModelSettings.id == 1)
            .values(data=data, updated_at=func.now())
        )
