import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession


class BaseDAO:
    model = None

    @classmethod
    async def find_all(cls, session: AsyncSession, **filters):
        """Все записи, опционально с фильтрами по полям"""
        result = await session.execute(select(cls.model).filter_by(**filters))
        return result.scalars().all()

    @classmethod
    async def find_one_or_none(cls, session: AsyncSession, **filters):
        """Одна запись по произвольным полям (None, если нет)"""
        result = await session.execute(select(cls.model).filter_by(**filters))
        return result.scalars().one_or_none()

    @classmethod
    async def find_by_id(cls, session: AsyncSession, id: uuid.UUID | int):
        """Запись по первичному ключу"""
        return await session.get(cls.model, id)

    @classmethod
    async def add(cls, session: AsyncSession, **values):
        """Создаёт запись и возвращает её"""
        obj = cls.model(**values)
        session.add(obj)
        await session.commit()
        await session.refresh(obj)
        return obj

    @classmethod
    async def update_by_id(cls, session: AsyncSession, id: uuid.UUID | int, **values):
        """Обновляет поля записи по id"""
        await session.execute(update(cls.model).where(cls.model.id == id).values(**values))
        await session.commit()

    @classmethod
    async def delete_by_id(cls, session: AsyncSession, id: uuid.UUID | int):
        """Удаляет запись по id"""
        await session.execute(delete(cls.model).where(cls.model.id == id))
        await session.commit()
