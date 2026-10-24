import uuid

from sqlalchemy import delete, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseDAO
from app.db.models.sessions import AuthSession


class SessionsDAO(BaseDAO):
    model = AuthSession

    @classmethod
    async def rotate_refresh_hash(
        cls, session: AsyncSession, session_id: uuid.UUID, old_hash: str, new_hash: str
    ) -> bool:
        """Атомарно меняет хэш refresh токена, только если в БД лежит old_hash; True, если замена прошла"""
        result = await session.execute(
            update(cls.model)
            .where(cls.model.id == session_id, cls.model.refresh_token_hash == old_hash)
            .values(refresh_token_hash=new_hash, previous_token_hash=old_hash, rotated_at=func.now())
            .returning(cls.model.id)
            .execution_options(synchronize_session=False)
        )
        rotated = result.scalar_one_or_none() is not None
        await session.commit()
        return rotated

    @classmethod
    async def delete_by_login(cls, session: AsyncSession, login: str):
        """Закрывает все сессии пользователя"""
        await session.execute(delete(cls.model).where(cls.model.login == login))
        await session.commit()

    @classmethod
    async def delete_expired(cls, session: AsyncSession):
        """Удаляет сессии с истёкшим сроком"""
        await session.execute(delete(cls.model).where(cls.model.expires_at < func.now()))
        await session.commit()
