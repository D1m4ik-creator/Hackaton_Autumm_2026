from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseDAO
from app.db.models.users import User


class UsersDAO(BaseDAO):
    model = User

    @classmethod
    async def find_by_login_or_email(cls, session: AsyncSession, value: str) -> User | None:
        """Пользователь по логину или почте (почта хранится в нижнем регистре)"""
        result = await session.execute(select(User).where(or_(User.login == value, User.email == value.lower())))
        return result.scalars().first()

    @classmethod
    async def list_all(cls, session: AsyncSession, role: str | None = None) -> list[User]:
        query = select(User).order_by(User.created_at, User.login)
        if role:
            query = query.where(User.role == role)
        result = await session.execute(query)
        return list(result.scalars().all())
