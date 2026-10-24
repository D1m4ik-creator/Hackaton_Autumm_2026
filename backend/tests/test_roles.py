"""Роли: администратор из .env создаёт менеджеров, менеджер видит клиентов, но не правит настройки."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.limiter import limiter
from app.main import app

ADMIN = {"login": "admin", "password": "test_password"}
MANAGER = {"login": "manager1", "email": "manager1@example.com", "password": "Passw0rd-1"}


async def _new_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def _login(client: AsyncClient, login: str, password: str) -> int:
    return (await client.post("/api/v1/auth/login", json={"login": login, "password": password})).status_code


@pytest.fixture
async def admin(client: AsyncClient) -> AsyncClient:
    assert await _login(client, ADMIN["login"], ADMIN["password"]) == 200
    return client


@pytest.fixture
async def manager(admin: AsyncClient):
    created = await admin.post("/api/v1/users", json=MANAGER)
    assert created.status_code == 201
    async with await _new_client() as m:
        assert await _login(m, MANAGER["login"], MANAGER["password"]) == 200
        yield m, created.json()["id"]


async def test_admin_me_has_role(admin: AsyncClient):
    assert (await admin.get("/api/v1/auth/me")).json()["role"] == "superadmin"


async def test_create_manager_and_login_by_login_or_email(admin: AsyncClient):
    created = await admin.post("/api/v1/users", json={**MANAGER, "email": "Manager1@Example.com"})
    assert created.status_code == 201
    assert created.json()["email"] == "manager1@example.com"
    assert "password" not in created.json() and "passwordHash" not in created.json()
    async with await _new_client() as m:
        assert await _login(m, "manager1@example.com", MANAGER["password"]) == 200
        assert (await m.get("/api/v1/auth/me")).json()["role"] == "manager"


async def test_wrong_password_and_unknown_user(admin: AsyncClient):
    await admin.post("/api/v1/users", json=MANAGER)
    async with await _new_client() as c:
        assert await _login(c, "manager1", "wrong-pass-1") == 401
        assert await _login(c, "nobody", "wrong-pass-1") == 401


async def test_duplicates_and_validation(admin: AsyncClient):
    await admin.post("/api/v1/users", json=MANAGER)
    assert (await admin.post("/api/v1/users", json={**MANAGER, "email": "x@example.com"})).status_code == 409
    assert (await admin.post("/api/v1/users", json={**MANAGER, "login": "manager2"})).status_code == 409
    assert (await admin.post("/api/v1/users", json={**MANAGER, "login": "admin", "email": "a@example.com"})).status_code == 409
    assert (await admin.post("/api/v1/users", json={**MANAGER, "login": "m3", "email": "m3@example.com", "password": "123"})).status_code == 422
    assert (await admin.post("/api/v1/users", json={"login": "manager4", "email": "bad", "password": "Passw0rd-1"})).status_code == 422


async def test_manager_can_view_but_not_change(manager):
    m, user_id = manager
    assert (await m.get("/api/v1/customers")).status_code == 200
    assert (await m.get("/api/v1/analytics/summary")).status_code == 200
    assert (await m.get("/api/v1/model/settings")).status_code == 200
    assert (await m.patch("/api/v1/model/settings", json={"asOf": None})).status_code == 403
    assert (await m.put("/api/v1/source/snapshot", json={"accounts": [], "services": [], "transactions": []})).status_code == 403
    assert (await m.get("/api/v1/users")).status_code == 403
    assert (await m.post("/api/v1/users", json={**MANAGER, "login": "evil1", "email": "e@example.com"})).status_code == 403
    assert (await m.delete(f"/api/v1/users/{user_id}")).status_code == 403


async def test_users_require_login(client: AsyncClient):
    assert (await client.get("/api/v1/users")).status_code == 401


async def test_manager_refresh_works(manager):
    m, _ = manager
    assert (await m.post("/api/v1/auth/refresh")).status_code == 200
    assert (await m.get("/api/v1/auth/me")).status_code == 200


async def test_deleted_manager_loses_access(admin: AsyncClient, manager):
    m, user_id = manager
    assert (await admin.delete(f"/api/v1/users/{user_id}")).status_code == 204
    assert (await m.get("/api/v1/auth/me")).status_code == 401
    assert (await m.post("/api/v1/auth/refresh")).status_code == 401
    async with await _new_client() as c:
        assert await _login(c, MANAGER["login"], MANAGER["password"]) == 401
    assert (await admin.delete(f"/api/v1/users/{user_id}")).status_code == 404


async def test_recreated_manager_rejects_old_token(admin: AsyncClient, manager):
    """Менеджера удалили и создали заново с тем же логином — старый access-токен (другой uid) не действует."""
    m, user_id = manager
    assert (await admin.delete(f"/api/v1/users/{user_id}")).status_code == 204
    recreated = await admin.post("/api/v1/users", json=MANAGER)
    assert recreated.status_code == 201
    assert recreated.json()["id"] != user_id
    # Старый токен ещё в cookie и по сроку жив, но несёт прежний uid
    assert (await m.get("/api/v1/auth/me")).status_code == 401


async def test_password_change_closes_old_sessions(admin: AsyncClient, manager):
    m, user_id = manager
    assert (await admin.patch(f"/api/v1/users/{user_id}", json={"password": "NewPassw0rd-2"})).status_code == 200
    assert (await m.post("/api/v1/auth/refresh")).status_code == 401
    async with await _new_client() as c:
        assert await _login(c, MANAGER["login"], MANAGER["password"]) == 401
        assert await _login(c, MANAGER["login"], "NewPassw0rd-2") == 200


async def test_login_rate_limit(client: AsyncClient):
    limiter.enabled = True
    limiter.reset()
    try:
        codes = [await _login(client, "admin", "wrong-pass-1") for _ in range(7)]
    finally:
        limiter.enabled = False
        limiter.reset()
    assert codes[:5] == [401] * 5
    assert codes[5:] == [429, 429]
