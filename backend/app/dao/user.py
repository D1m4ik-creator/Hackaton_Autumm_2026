import uuid

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .base import BaseDAO
from app.db.models.users import User


class UsersDAO(BaseDAO):
    model = User

    # Варианты без commit: позволяют crud закрыть смену/удаление пользователя и его сессии одной транзакцией

    @classmethod
    async def update_by_id_no_commit(cls, session: AsyncSession, id: uuid.UUID, **values) -> None:
        """Обновляет поля пользователя без commit (коммит делает crud)"""
        await session.execute(update(User).where(User.id == id).values(**values))

    @classmethod
    async def lock_login(cls, session: AsyncSession, id: uuid.UUID) -> str | None:
        """Блокирует строку пользователя до конца транзакции (FOR UPDATE) и возвращает его текущий логин"""
        result = await session.execute(select(User.login).where(User.id == id).with_for_update())
        return result.scalar_one_or_none()

    @classmethod
    async def delete_by_id_no_commit(cls, session: AsyncSession, id: uuid.UUID) -> None:
        """Удаляет пользователя без commit (коммит делает crud)"""
        await session.execute(delete(User).where(User.id == id))

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
