import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseDAO
from app.db.models.users import User


class UsersDAO(BaseDAO):
    model = User

    @classmethod
    async def set_refresh_token_hash(cls, session: AsyncSession, user_id: uuid.UUID, token_hash: str | None):
        """Сохраняет хэш актуального refresh токена (None, чтобы сбросить)"""
        await cls.update_by_id(session, user_id, refresh_token_hash=token_hash)
