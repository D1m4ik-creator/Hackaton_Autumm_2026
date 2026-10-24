"""Проверка миграций Alembic на отдельной пустой базе.

Тест накатывает миграции с нуля на отдельную базу ``hackathon_mig_test``
(рабочую тестовую базу не трогаем), проверяет состав таблиц и строки-синглтоны,
прогоняет полный откат и повторный накат, и сверяет схему моделей со схемой,
которую строят миграции (``compare_metadata`` не должен находить расхождений).

Тест синхронный: ``alembic.command`` сам вызывает ``asyncio.run`` внутри env.py,
поэтому запускать его из работающего цикла нельзя. ``get_settings`` закэширован
на рабочую тестовую базу — на время теста подменяем ``POSTGRES_DB`` и чистим кэш,
в конце возвращаем прежнее значение.
"""

import asyncio
import os
from pathlib import Path

import asyncpg
import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config as AlembicConfig
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.db.models import Base

MIG_DB = "hackathon_mig_test"

# Путь к alembic.ini — абсолютный, от расположения backend/: тест должен
# работать при запуске pytest из любой рабочей директории (script_location
# в alembic.ini задан через %(here)s, поэтому раскроется корректно).
ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"

# Таблицы, которые должны появиться после наката всех миграций.
EXPECTED_TABLES = {
    "alembic_version",
    "auth_sessions",
    "users",
    "accounts",
    "services",
    "transactions",
    "model_settings",
    "risk_results",
    "risk_summary",
}


async def _server_params() -> dict:
    db = get_settings().database
    return dict(
        user=db.user,
        password=db.password.get_secret_value(),
        host=db.host,
        port=db.port,
    )


async def _recreate_database(params: dict) -> None:
    conn = await asyncpg.connect(database="postgres", **params)
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{MIG_DB}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{MIG_DB}"')
    finally:
        await conn.close()


async def _drop_database(params: dict) -> None:
    conn = await asyncpg.connect(database="postgres", **params)
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{MIG_DB}" WITH (FORCE)')
    finally:
        await conn.close()


async def _table_names(url: str) -> set[str]:
    engine = create_async_engine(url, poolclass=sa.pool.NullPool)
    try:
        async with engine.connect() as conn:
            return await conn.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))
    finally:
        await engine.dispose()


async def _inspect_full(url: str) -> tuple[set[str], dict[str, int], list]:
    """Таблицы, число строк-синглтонов и расхождение схемы с моделями."""
    engine = create_async_engine(url, poolclass=sa.pool.NullPool)
    try:
        async with engine.connect() as conn:
            tables = await conn.run_sync(lambda sc: set(inspect(sc).get_table_names()))
            singletons: dict[str, int] = {}
            for table in ("model_settings", "risk_summary"):
                result = await conn.exec_driver_sql(f"SELECT count(*) FROM {table} WHERE id = 1")
                singletons[table] = result.scalar()
            diff = await conn.run_sync(
                lambda sc: compare_metadata(
                    MigrationContext.configure(sc, opts={"compare_type": True}),
                    Base.metadata,
                )
            )
        return tables, singletons, diff
    finally:
        await engine.dispose()


def test_migrations_apply_rollback_and_match_models():
    assert MIG_DB.endswith("_test"), "база миграций должна оканчиваться на _test"

    saved_db = os.environ.get("POSTGRES_DB")
    get_settings.cache_clear()
    params = asyncio.run(_server_params())  # user/password/host/port из текущих настроек

    os.environ["POSTGRES_DB"] = MIG_DB
    get_settings.cache_clear()
    try:
        url = get_settings().database.get_db_url()
        config = AlembicConfig(str(ALEMBIC_INI))

        # Накат с нуля
        asyncio.run(_recreate_database(params))
        command.upgrade(config, "head")

        tables, singletons, diff = asyncio.run(_inspect_full(url))
        assert EXPECTED_TABLES <= tables, f"после upgrade не хватает таблиц: {EXPECTED_TABLES - tables}"
        assert singletons == {"model_settings": 1, "risk_summary": 1}, singletons
        assert diff == [], f"схема моделей расходится с миграциями: {diff}"

        # Полный откат: доменные таблицы исчезают
        command.downgrade(config, "base")
        after_down = asyncio.run(_table_names(url))
        assert "accounts" not in after_down and "users" not in after_down, after_down

        # Повторный накат даёт ту же схему без расхождений
        command.upgrade(config, "head")
        tables2, singletons2, diff2 = asyncio.run(_inspect_full(url))
        assert EXPECTED_TABLES <= tables2
        assert singletons2 == {"model_settings": 1, "risk_summary": 1}, singletons2
        assert diff2 == [], f"схема расходится после повторного наката: {diff2}"
    finally:
        asyncio.run(_drop_database(params))
        if saved_db is None:
            os.environ.pop("POSTGRES_DB", None)
        else:
            os.environ["POSTGRES_DB"] = saved_db
        get_settings.cache_clear()
