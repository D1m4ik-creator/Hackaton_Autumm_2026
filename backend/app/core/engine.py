from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database.get_db_url(),
    echo=settings.database.echo,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def get_read_session() -> AsyncIterator[AsyncSession]:
    """Сессия только для чтения: одна транзакция REPEATABLE READ READ ONLY.

    Все SELECT одного запроса видят единый снимок, поэтому ответ не смешивает
    версии данных даже при параллельной замене снимка. Уровень изоляции и
    READ ONLY сбрасываются при возврате соединения в пул.
    """
    async with SessionLocal() as session:
        await session.connection(
            execution_options={
                "isolation_level": "REPEATABLE READ",
                "postgresql_readonly": True,
            }
        )
        yield session


async def close_engine() -> None:
    await engine.dispose()


SessionDep = Annotated[AsyncSession, Depends(get_session)]
ReadSessionDep = Annotated[AsyncSession, Depends(get_read_session)]
