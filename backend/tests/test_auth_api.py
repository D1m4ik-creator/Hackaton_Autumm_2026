"""Интеграционные тесты API: /api/v1/health и /api/v1/auth/*.

Ходят через ASGI-транспорт в реальный PostgreSQL (тестовая база hackathon_test),
поэтому проверяется весь путь: роутер -> CRUD -> DAO -> БД.
"""

import uuid
from datetime import datetime, timedelta, timezone

from httpx import ASGITransport, AsyncClient
from sqlalchemy import update

from app.core.security import ACCESS_COOKIE, REFRESH_COOKIE, create_refresh_token
from app.db.models import AuthSession
from app.main import app

ADMIN = {"login": "admin", "password": "test_password"}


def _client_with_refresh(refresh_token: str) -> AsyncClient:
    """Отдельный «браузер» с заданным refresh токеном."""
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")
    client.cookies.set(REFRESH_COOKIE, refresh_token)
    return client


async def test_health(client: AsyncClient):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_login_success_sets_cookies(client: AsyncClient):
    response = await client.post("/api/v1/auth/login", json=ADMIN)

    assert response.status_code == 200
    assert response.json() == {"message": "Успешная авторизация"}
    # Оба токена выставлены в httponly-cookie
    assert client.cookies.get(ACCESS_COOKIE)
    assert client.cookies.get(REFRESH_COOKIE)
    set_cookie = response.headers.get_list("set-cookie")
    assert any(ACCESS_COOKIE in c and "httponly" in c.lower() for c in set_cookie)
    assert any(REFRESH_COOKIE in c and "httponly" in c.lower() for c in set_cookie)


async def test_login_wrong_credentials(client: AsyncClient):
    for body in (
        {"login": "admin", "password": "wrong"},
        {"login": "nobody", "password": "test_password"},
    ):
        response = await client.post("/api/v1/auth/login", json=body)
        assert response.status_code == 401
    assert not client.cookies.get(ACCESS_COOKIE)


async def test_me_requires_token(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_me_after_login(client: AsyncClient):
    await client.post("/api/v1/auth/login", json=ADMIN)

    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json() == {"login": "admin", "role": "superadmin", "email": None}


async def test_refresh_without_cookie(client: AsyncClient):
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 401


async def test_refresh_rotates_tokens(client: AsyncClient):
    await client.post("/api/v1/auth/login", json=ADMIN)
    old_refresh = client.cookies.get(REFRESH_COOKIE)

    response = await client.post("/api/v1/auth/refresh")

    assert response.status_code == 200
    new_refresh = client.cookies.get(REFRESH_COOKIE)
    assert new_refresh and new_refresh != old_refresh


async def test_reusing_old_refresh_kills_session(client: AsyncClient, db_session):
    """Повторное использование давно заменённого refresh — кража: сессия закрывается целиком."""
    await client.post("/api/v1/auth/login", json=ADMIN)
    old_refresh = client.cookies.get(REFRESH_COOKIE)

    # Первая ротация проходит
    assert (await client.post("/api/v1/auth/refresh")).status_code == 200

    # «Состариваем» ротацию, чтобы повтор старого токена не попал в grace-окно
    await db_session.execute(
        update(AuthSession).values(rotated_at=datetime.now(timezone.utc) - timedelta(minutes=5))
    )
    await db_session.commit()

    # Повтор старого токена из другого «браузера» — сессия закрывается
    thief = _client_with_refresh(old_refresh)
    response = await thief.post("/api/v1/auth/refresh")
    assert response.status_code == 401
    await thief.aclose()

    # Сессия закрыта: даже актуальный refresh больше не работает
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 401
    assert response.json()["detail"] == "Refresh token не действителен"


async def test_parallel_refresh_within_grace_gets_access_only(client: AsyncClient):
    """Параллельный запрос с тем же refresh сразу после ротации — не кража:
    отдаётся только access, refresh остаётся у первого запроса."""
    await client.post("/api/v1/auth/login", json=ADMIN)
    old_refresh = client.cookies.get(REFRESH_COOKIE)

    # Первый запрос заменил refresh
    assert (await client.post("/api/v1/auth/refresh")).status_code == 200

    # Второй параллельный запрос из того же браузера пришёл со старым токеном
    twin = _client_with_refresh(old_refresh)
    response = await twin.post("/api/v1/auth/refresh")
    assert response.status_code == 200
    # Новый refresh не выдаётся второй раз
    assert REFRESH_COOKIE not in {
        c.split("=")[0] for c in response.headers.get_list("set-cookie")
    }
    await twin.aclose()


async def test_refresh_with_forged_token(client: AsyncClient):
    """Refresh с чужим sid: сессии нет, подпись валидна, но 401."""
    forged = create_refresh_token({"sub": "admin", "sid": str(uuid.uuid4())})
    client.cookies.set(REFRESH_COOKIE, forged)

    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 401


async def test_logout_clears_cookies_and_session(client: AsyncClient):
    await client.post("/api/v1/auth/login", json=ADMIN)
    old_refresh = client.cookies.get(REFRESH_COOKIE)

    response = await client.post("/api/v1/auth/logout")

    assert response.status_code == 200
    assert not client.cookies.get(ACCESS_COOKIE)
    assert not client.cookies.get(REFRESH_COOKIE)
    assert (await client.get("/api/v1/auth/me")).status_code == 401

    # Сессия удалена и на сервере: старый refresh не воскрешает её
    ghost = _client_with_refresh(old_refresh)
    assert (await ghost.post("/api/v1/auth/refresh")).status_code == 401
    await ghost.aclose()


async def test_logout_without_cookies_is_safe(client: AsyncClient):
    """Logout без токенов не падает."""
    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 200
