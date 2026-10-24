"""Общие фикстуры: тестовая БД в PostgreSQL из docker-compose и HTTP-клиент к приложению.

Тесты ходят в реальный PostgreSQL (модель AuthSession использует тип UUID
из диалекта PostgreSQL, на SQLite схема не собирается). По умолчанию
адрес совпадает с БД из корневого docker-compose.yaml (localhost:5433);
все значения можно переопределить переменными окружения.

Работа идёт в отдельной базе hackathon_test: она создаётся перед прогоном
и удаляется после, рабочие данные не затрагиваются.
"""

import os

# Переменные должны быть выставлены до первого импорта app.*:
# app.core.engine создаёт engine из настроек в момент импорта модуля.
# Переменные окружения имеют приоритет над backend/.env.
os.environ.setdefault("POSTGRES_USER", "postgres")
os.environ.setdefault("POSTGRES_PASSWORD", "change_me")
# Принудительно тестовая база: тесты её удаляют и создают заново, рабочую трогать нельзя
os.environ["POSTGRES_DB"] = os.environ.get("TEST_POSTGRES_DB", "hackathon_test")
assert os.environ["POSTGRES_DB"].endswith("_test"), "тестовая база должна оканчиваться на _test"
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5433")
os.environ.setdefault("JWT_SECRET_KEY", "0" * 64)
os.environ.setdefault("SESSION_SECRET_KEY", "2" * 64)
os.environ.setdefault("JWT_REFRESH_SECRET_KEY", "1" * 64)
os.environ.setdefault("ADMIN_LOGIN", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "test_password")
# Лимиты на вход мешают тестам, где логинятся много раз; их проверяет отдельный тест
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import asyncpg  # noqa: E402
import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import delete  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.engine import SessionLocal, engine  # noqa: E402
from app.db.models import AuthSession, Base, ModelSettings, RiskSummary, User  # noqa: E402
from app.main import app  # noqa: E402


async def _recreate_test_database() -> None:
    """Создаёт пустую тестовую базу (удаляя старую, если осталась от прошлого прогона)."""
    settings = get_settings().database
    conn = await asyncpg.connect(
        user=settings.user,
        password=settings.password.get_secret_value(),
        host=settings.host,
        port=settings.port,
        database="postgres",
    )
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{settings.db}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{settings.db}"')
    finally:
        await conn.close()


async def _drop_test_database() -> None:
    settings = get_settings().database
    conn = await asyncpg.connect(
        user=settings.user,
        password=settings.password.get_secret_value(),
        host=settings.host,
        port=settings.port,
        database="postgres",
    )
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{settings.db}" WITH (FORCE)')
    finally:
        await conn.close()


@pytest.fixture(scope="session", autouse=True)
async def _setup_database():
    """Свежая тестовая БД со схемой из моделей на весь прогон тестов."""
    await _recreate_test_database()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Одиночные строки, которые в рабочей базе создаёт миграция
    async with SessionLocal() as session:
        session.add_all([ModelSettings(id=1), RiskSummary(id=1)])
        await session.commit()
    yield
    # Сначала закрываем соединения пула, иначе база не удалится
    await engine.dispose()
    await _drop_test_database()


@pytest.fixture
async def db_session():
    """Чистая сессия БД; таблицы сессий и менеджеров очищаются перед каждым тестом."""
    async with SessionLocal() as session:
        await session.execute(delete(AuthSession))
        await session.execute(delete(User))
        await session.commit()
        yield session


@pytest.fixture
async def client(db_session):
    """HTTP-клиент к приложению без поднятия сервера; cookie-сессия чистая на каждый тест.

    Фикстура зависит от db_session, чтобы гарантировать чистую таблицу
    auth_sessions перед тестом.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac
