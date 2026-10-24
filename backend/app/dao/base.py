import uuid
from collections.abc import Sequence

from sqlalchemy import Row, delete, func, insert, select, update
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

    # Методы для снимка исходных данных и пересчёта: без commit, коммит делает crud

    @classmethod
    async def load_rows(cls, session: AsyncSession) -> Sequence[Row]:
        """Все строки таблицы, отсортированные по id (для загрузки снимка в память)"""
        table = cls.model.__table__
        result = await session.execute(select(table).order_by(table.c.id))
        return result.all()

    @classmethod
    async def bulk_insert(cls, session: AsyncSession, rows: list[dict], chunk: int = 5000) -> None:
        """Пакетная вставка словарей без commit"""
        if not rows:
            return
        table = cls.model.__table__
        for start in range(0, len(rows), chunk):
            await session.execute(insert(table), rows[start : start + chunk])

    @classmethod
    async def delete_all(cls, session: AsyncSession) -> None:
        """Удаляет все строки таблицы без commit"""
        await session.execute(delete(cls.model))

    @classmethod
    async def count(cls, session: AsyncSession) -> int:
        """Число строк в таблице"""
        result = await session.execute(select(func.count()).select_from(cls.model))
        return result.scalar_one()
