"""Иерархия ролей: суперадмин (из .env) -> админы -> менеджеры; менеджеры только смотрят клиентов."""

import json
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

SNAPSHOT = json.loads((Path(__file__).resolve().parents[2] / "origin_data" / "data.json").read_text(encoding="utf-8"))
SUPERADMIN = {"login": "admin", "password": "test_password"}
ADMIN = {"login": "boss1", "email": "boss1@example.com", "password": "Passw0rd-1", "role": "admin"}
MANAGER = {"login": "manager1", "email": "manager1@example.com", "password": "Passw0rd-2"}


@asynccontextmanager
async def _client_for(login: str, password: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        assert (await c.post("/api/v1/auth/login", json={"login": login, "password": password})).status_code == 200
        yield c


@pytest.fixture
async def superadmin(client: AsyncClient) -> AsyncClient:
    assert (await client.post("/api/v1/auth/login", json=SUPERADMIN)).status_code == 200
    return client


@pytest.fixture
async def admin(superadmin: AsyncClient):
    created = await superadmin.post("/api/v1/users", json=ADMIN)
    assert created.status_code == 201
    assert created.json()["role"] == "admin"
    async with _client_for(ADMIN["login"], ADMIN["password"]) as a:
        yield a, created.json()["id"]


async def test_superadmin_me_and_admin_creation(superadmin: AsyncClient):
    assert (await superadmin.get("/api/v1/auth/me")).json()["role"] == "superadmin"
    created = await superadmin.post("/api/v1/users", json=ADMIN)
    assert created.status_code == 201 and created.json()["role"] == "admin"


async def test_admin_logs_in_and_manages_managers(admin):
    a, _ = admin
    assert (await a.get("/api/v1/auth/me")).json()["role"] == "admin"
    created = await a.post("/api/v1/users", json=MANAGER)
    assert created.status_code == 201 and created.json()["role"] == "manager"
    assert (await a.patch(f"/api/v1/users/{created.json()['id']}", json={"email": "new1@example.com"})).status_code == 200
    assert (await a.delete(f"/api/v1/users/{created.json()['id']}")).status_code == 204


async def test_admin_cannot_create_or_touch_admins(superadmin: AsyncClient, admin):
    a, admin_id = admin
    assert (await a.post("/api/v1/users", json={**ADMIN, "login": "boss2", "email": "boss2@example.com"})).status_code == 403
    assert (await a.patch(f"/api/v1/users/{admin_id}", json={"email": "x@example.com"})).status_code == 403
    assert (await a.delete(f"/api/v1/users/{admin_id}")).status_code == 403


async def test_users_list_visibility(superadmin: AsyncClient, admin):
    a, _ = admin
    await a.post("/api/v1/users", json=MANAGER)
    assert {u["role"] for u in (await a.get("/api/v1/users")).json()} == {"manager"}
    assert {u["role"] for u in (await superadmin.get("/api/v1/users")).json()} == {"admin", "manager"}


async def test_admin_can_change_model_and_data_but_manager_cannot(superadmin: AsyncClient, admin):
    a, _ = admin
    assert (await a.put("/api/v1/source/snapshot", json=SNAPSHOT)).status_code == 200
    assert (await a.patch("/api/v1/model/settings", json={"asOf": "2026-10-19T15:00:00Z"})).status_code == 200
    await a.post("/api/v1/users", json=MANAGER)
    async with _client_for(MANAGER["login"], MANAGER["password"]) as m:
        assert (await m.get("/api/v1/customers")).status_code == 200
        assert (await m.patch("/api/v1/model/settings", json={"asOf": None})).status_code == 403
        assert (await m.put("/api/v1/source/snapshot", json=SNAPSHOT)).status_code == 403
        assert (await m.get("/api/v1/users")).status_code == 403
        assert (await m.post("/api/v1/users", json={**MANAGER, "login": "evil1", "email": "e@example.com"})).status_code == 403


async def test_deleted_admin_loses_access(superadmin: AsyncClient, admin):
    a, admin_id = admin
    assert (await superadmin.delete(f"/api/v1/users/{admin_id}")).status_code == 204
    assert (await a.get("/api/v1/auth/me")).status_code == 401
    assert (await a.get("/api/v1/users")).status_code == 401


async def test_manager_cannot_become_admin_via_create(superadmin: AsyncClient):
    assert (await superadmin.post("/api/v1/users", json={**MANAGER, "role": "superadmin"})).status_code == 422
