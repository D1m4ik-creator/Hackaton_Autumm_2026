"""Синхронизация пользователей панели в Authentik: создание, изменение, удаление и сбои API."""

import json

import httpx
import pytest
from httpx import AsyncClient
from pydantic import SecretStr

import app.core.authentik_api as authentik_api
from app.core.config import get_settings

ADMIN = {"login": "admin", "password": "test_password"}
MANAGER = {"login": "manager1", "email": "manager1@example.com", "password": "Passw0rd-1"}


class FakeAuthentik:
    """Минимальный /api/v3/core/users/ в памяти"""

    def __init__(self) -> None:
        self.users: dict[int, dict] = {}
        self.passwords: dict[int, str] = {}
        self.next_pk = 1
        self.down = False

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            return httpx.Response(503)
        assert request.headers["authorization"] == "Bearer test-token"
        path = request.url.path.removeprefix("/api/v3/core/users/").strip("/")
        if request.method == "GET" and not path:
            username = request.url.params.get("username")
            return httpx.Response(200, json={"results": [u for u in self.users.values() if u["username"] == username]})
        if request.method == "POST" and not path:
            pk, self.next_pk = self.next_pk, self.next_pk + 1
            self.users[pk] = {**json.loads(request.content), "pk": pk}
            return httpx.Response(201, json=self.users[pk])
        pk_text, _, action = path.partition("/")
        pk = int(pk_text)
        if pk not in self.users:
            return httpx.Response(404)
        if request.method == "PATCH":
            self.users[pk].update(json.loads(request.content))
            return httpx.Response(200, json=self.users[pk])
        if request.method == "POST" and action == "set_password":
            self.passwords[pk] = json.loads(request.content)["password"]
            return httpx.Response(204)
        if request.method == "DELETE":
            del self.users[pk]
            self.passwords.pop(pk, None)
            return httpx.Response(204)
        return httpx.Response(405)

    def by_username(self, username: str) -> dict | None:
        return next((u for u in self.users.values() if u["username"] == username), None)


@pytest.fixture
def authentik(monkeypatch) -> FakeAuthentik:
    fake = FakeAuthentik()
    monkeypatch.setattr(get_settings(), "authentik_api_url", "http://authentik.test")
    monkeypatch.setattr(get_settings(), "authentik_api_token", SecretStr("test-token"))
    monkeypatch.setattr(
        authentik_api,
        "_client",
        lambda: httpx.AsyncClient(
            transport=httpx.MockTransport(fake.handler),
            base_url="http://authentik.test/api/v3",
            headers={"Authorization": "Bearer test-token"},
        ),
    )
    return fake


@pytest.fixture
async def admin(client: AsyncClient) -> AsyncClient:
    assert (await client.post("/api/v1/auth/login", json=ADMIN)).status_code == 200
    return client


async def test_create_update_delete_are_mirrored(admin: AsyncClient, authentik: FakeAuthentik):
    created = await admin.post("/api/v1/users", json=MANAGER)
    assert created.status_code == 201
    user = authentik.by_username("manager1")
    assert user and user["email"] == "manager1@example.com" and user["path"] == authentik_api.USER_PATH
    assert authentik.passwords[user["pk"]] == MANAGER["password"]

    user_id = created.json()["id"]
    patched = await admin.patch(f"/api/v1/users/{user_id}", json={"login": "manager2", "password": "New-Passw0rd"})
    assert patched.status_code == 200
    assert authentik.by_username("manager1") is None
    assert authentik.by_username("manager2")["pk"] == user["pk"]
    assert authentik.passwords[user["pk"]] == "New-Passw0rd"

    assert (await admin.delete(f"/api/v1/users/{user_id}")).status_code == 204
    assert authentik.users == {}


async def test_update_creates_missing_authentik_user(admin: AsyncClient, authentik: FakeAuthentik):
    """Пользователь, созданный до включения синхронизации, появляется в Authentik при смене пароля"""
    user_id = (await admin.post("/api/v1/users", json=MANAGER)).json()["id"]
    authentik.users.clear()

    assert (await admin.patch(f"/api/v1/users/{user_id}", json={"password": "New-Passw0rd"})).status_code == 200
    user = authentik.by_username("manager1")
    assert user and authentik.passwords[user["pk"]] == "New-Passw0rd"


async def test_authentik_down_on_create_keeps_panel_unchanged(admin: AsyncClient, authentik: FakeAuthentik):
    authentik.down = True
    response = await admin.post("/api/v1/users", json=MANAGER)
    assert response.status_code == 502
    assert (await admin.get("/api/v1/users")).json() == []


async def test_authentik_down_on_update_rolls_back(admin: AsyncClient, authentik: FakeAuthentik):
    user_id = (await admin.post("/api/v1/users", json=MANAGER)).json()["id"]
    authentik.down = True
    assert (await admin.patch(f"/api/v1/users/{user_id}", json={"login": "manager2"})).status_code == 502
    assert [u["login"] for u in (await admin.get("/api/v1/users")).json()] == ["manager1"]
    # Пароль в панели тоже не сменился
    authentik.down = False
    async with AsyncClient(transport=admin._transport, base_url="http://testserver") as m:
        assert (await m.post("/api/v1/auth/login", json={"login": "manager1", "password": MANAGER["password"]})).status_code == 200


async def test_authentik_down_on_delete_still_deletes_in_panel(admin: AsyncClient, authentik: FakeAuthentik):
    user_id = (await admin.post("/api/v1/users", json=MANAGER)).json()["id"]
    authentik.down = True
    assert (await admin.delete(f"/api/v1/users/{user_id}")).status_code == 204
    assert (await admin.get("/api/v1/users")).json() == []


async def test_sync_disabled_makes_no_calls(admin: AsyncClient, monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("Authentik не должен вызываться при выключенной синхронизации")

    monkeypatch.setattr(authentik_api, "_client", fail)
    assert not get_settings().authentik_sync_enabled
    created = await admin.post("/api/v1/users", json=MANAGER)
    assert created.status_code == 201
    user_id = created.json()["id"]
    assert (await admin.patch(f"/api/v1/users/{user_id}", json={"password": "New-Passw0rd"})).status_code == 200
    assert (await admin.delete(f"/api/v1/users/{user_id}")).status_code == 204
