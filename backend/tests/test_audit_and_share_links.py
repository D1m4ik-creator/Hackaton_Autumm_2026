"""Аудит изменений настроек модели и публичные read-only ссылки на отчёт."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.limiter import limiter
from app.db.models import ShareLink
from app.db.models.audit import AuditLog
from app.main import app

SNAPSHOT = json.loads((Path(__file__).resolve().parents[2] / "origin_data" / "data.json").read_text(encoding="utf-8"))
ADMIN = {"login": "admin", "password": "test_password"}


@pytest.fixture
async def admin(client: AsyncClient) -> AsyncClient:
    assert (await client.post("/api/v1/auth/login", json=ADMIN)).status_code == 200
    return client


@pytest.fixture
async def loaded(admin: AsyncClient):
    # model_settings — синглтон-таблица, между тестами не пересоздаётся (в
    # отличие от accounts/services/transactions, которые PUT ниже заменяет
    # заново каждый раз) — тесты этого файла правят веса/bias, поэтому снимаем
    # и возвращаем исходные settings, чтобы не задеть другие файлы тестов.
    response = await admin.put("/api/v1/source/snapshot", json=SNAPSHOT)
    assert response.status_code == 200
    original = (await admin.get("/api/v1/model/settings")).json()["settings"]
    yield admin
    await admin.patch("/api/v1/model/settings", json={"weights": original["weights"], "bias": original["bias"]})


@pytest.fixture
async def manager(admin: AsyncClient) -> AsyncClient:
    created = await admin.post(
        "/api/v1/users", json={"login": "mgr-audit", "email": "mgr-audit@example.com", "password": "Passw0rd-1"}
    )
    assert created.status_code == 201
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        assert (await client.post("/api/v1/auth/login", json={"login": "mgr-audit", "password": "Passw0rd-1"})).status_code == 200
        yield client


# --- Аудит ---------------------------------------------------------------

async def test_patch_settings_writes_audit_entry(loaded: AsyncClient):
    patched = await loaded.patch("/api/v1/model/settings", json={"weights": {"has_prolong_wait": 2.5}})
    assert patched.status_code == 200

    audit = (await loaded.get("/api/v1/model/settings/audit")).json()
    assert audit["total"] >= 1
    entry = audit["items"][0]
    assert entry["action"] == "patch"
    assert entry["actorLogin"] == "admin"
    assert entry["actorRole"] == "superadmin"
    assert entry["before"]["weights"]["has_prolong_wait"] != 2.5
    assert entry["after"]["weights"]["has_prolong_wait"] == 2.5


async def test_delete_setting_writes_audit_entry_with_section(loaded: AsyncClient):
    deleted = await loaded.delete("/api/v1/model/settings/weights/has_prolong_wait")
    assert deleted.status_code == 200

    audit = (await loaded.get("/api/v1/model/settings/audit")).json()
    entry = audit["items"][0]
    assert entry["action"] == "delete"
    assert entry["section"] == "weights.has_prolong_wait"
    assert "has_prolong_wait" in entry["before"]["weights"]
    assert "has_prolong_wait" not in entry["after"]["weights"]


async def test_audit_superadmin_change_has_no_user_id(loaded: AsyncClient, db_session):
    await loaded.patch("/api/v1/model/settings", json={"bias": -2.0})
    row = (await db_session.execute(select(AuditLog).order_by(AuditLog.id.desc()))).scalars().first()
    assert row.actor_login == "admin"
    assert row.actor_role == "superadmin"
    assert row.user_id is None


async def test_audit_pagination(loaded: AsyncClient):
    for value in (1.0, 1.1, 1.2):
        assert (await loaded.patch("/api/v1/model/settings", json={"bias": value})).status_code == 200

    page1 = (await loaded.get("/api/v1/model/settings/audit?page=1&pageSize=2")).json()
    assert len(page1["items"]) == 2
    assert page1["page"] == 1
    assert page1["total"] >= 3
    page2 = (await loaded.get("/api/v1/model/settings/audit?page=2&pageSize=2")).json()
    assert page1["items"][0]["id"] != page2["items"][0]["id"]


async def test_audit_requires_admin(manager: AsyncClient):
    assert (await manager.get("/api/v1/model/settings/audit")).status_code == 403


# --- Публичная read-only ссылка ------------------------------------------

async def test_create_and_use_share_link(loaded: AsyncClient):
    created = await loaded.post("/api/v1/share-links", json={"label": "для жюри"})
    assert created.status_code == 200
    body = created.json()
    token = body["token"]
    assert body["active"] is True

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as anon:
        summary = await anon.get(f"/api/v1/public/report/summary?token={token}")
        assert summary.status_code == 200

        customers = await anon.get(f"/api/v1/public/report/customers?token={token}")
        assert customers.status_code == 200
        items = customers.json()["items"]
        assert items
        assert all("email" not in item for item in items)

        card = await anon.get(f"/api/v1/public/report/customers/1?token={token}")
        assert card.status_code == 200
        assert "email" not in card.json()


async def test_share_link_without_token_rejected(loaded: AsyncClient):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as anon:
        assert (await anon.get("/api/v1/public/report/summary")).status_code == 422
        assert (await anon.get("/api/v1/public/report/summary?token=garbage")).status_code == 401


async def test_revoked_share_link_rejected(loaded: AsyncClient):
    created = (await loaded.post("/api/v1/share-links", json={})).json()
    token, link_id = created["token"], created["id"]

    revoked = await loaded.delete(f"/api/v1/share-links/{link_id}")
    assert revoked.status_code == 200

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as anon:
        assert (await anon.get(f"/api/v1/public/report/summary?token={token}")).status_code == 401

    links = (await loaded.get("/api/v1/share-links")).json()
    assert next(link for link in links if link["id"] == link_id)["active"] is False


async def test_expired_share_link_rejected(loaded: AsyncClient, db_session):
    created = (await loaded.post("/api/v1/share-links", json={})).json()
    token, link_id = created["token"], created["id"]

    await db_session.execute(
        ShareLink.__table__.update().where(ShareLink.id == link_id).values(
            expires_at=datetime.now(timezone.utc) - timedelta(days=1)
        )
    )
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as anon:
        assert (await anon.get(f"/api/v1/public/report/summary?token={token}")).status_code == 401


async def test_share_links_require_admin(manager: AsyncClient):
    assert (await manager.post("/api/v1/share-links", json={})).status_code == 403
    assert (await manager.get("/api/v1/share-links")).status_code == 403
    assert (await manager.delete("/api/v1/share-links/00000000-0000-0000-0000-000000000000")).status_code == 403


async def test_public_report_rate_limited(loaded: AsyncClient):
    created = (await loaded.post("/api/v1/share-links", json={})).json()
    token = created["token"]

    limiter.enabled = True
    limiter.reset()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as anon:
            codes = [
                (await anon.get(f"/api/v1/public/report/summary?token={token}")).status_code
                for _ in range(31)
            ]
    finally:
        limiter.enabled = False
        limiter.reset()

    assert codes.count(429) > 0
