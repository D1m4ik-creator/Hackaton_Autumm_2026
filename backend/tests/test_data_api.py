"""Данные и права: снимок, список клиентов, сводка, метрики, настройки модели, проверки конфига и сессий."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import select, update

from app.core.config import Config
from app.db.models import AuthSession
from app.main import app  # noqa: F401  (подключает все модели)

SNAPSHOT = json.loads((Path(__file__).resolve().parents[2] / "origin_data" / "data.json").read_text(encoding="utf-8"))
ADMIN = {"login": "admin", "password": "test_password"}


@pytest.fixture
async def admin(client: AsyncClient) -> AsyncClient:
    assert (await client.post("/api/v1/auth/login", json=ADMIN)).status_code == 200
    return client


@pytest.fixture
async def loaded(admin: AsyncClient) -> AsyncClient:
    response = await admin.put("/api/v1/source/snapshot", json=SNAPSHOT)
    assert response.status_code == 200
    return admin


async def test_put_snapshot_loads_and_recalculates(admin: AsyncClient):
    response = await admin.put("/api/v1/source/snapshot", json=SNAPSHOT)
    assert response.status_code == 200
    body = response.json()
    assert (body["accounts"], body["services"], body["transactions"]) == (10, 30, 100)

    summary = (await admin.get("/api/v1/analytics/summary")).json()
    assert summary["customersTotal"] == 10
    assert summary["version"] == body["version"]
    metrics = (await admin.get("/metrics")).text
    assert f"churn_recalculations_total {body['version']}" in metrics
    assert 'churn_customers{level="no_data"} 10' in metrics


async def test_invalid_snapshots_do_not_touch_data(loaded: AsyncClient):
    broken_owner = json.loads(json.dumps(SNAPSHOT))
    broken_owner["services"][0]["ownerId"] = 999
    duplicate_id = json.loads(json.dumps(SNAPSHOT))
    duplicate_id["accounts"][1]["id"] = duplicate_id["accounts"][0]["id"]
    too_big = json.loads(json.dumps(SNAPSHOT))
    too_big["accounts"][0]["balance"] = 2**63
    for bad in (broken_owner, duplicate_id, too_big):
        assert (await loaded.put("/api/v1/source/snapshot", json=bad)).status_code == 422
    assert (await loaded.get("/api/v1/customers")).json()["total"] == 10


async def test_customers_sorting_filter_and_card(loaded: AsyncClient):
    by_balance = (await loaded.get("/api/v1/customers?sort=balance&order=desc")).json()["items"]
    balances = [c["balance"] for c in by_balance]
    assert balances == sorted(balances, reverse=True)
    assert [c["id"] for c in (await loaded.get("/api/v1/customers?sort=id&order=asc&pageSize=3&page=2")).json()["items"]] == [4, 5, 6]
    assert (await loaded.get("/api/v1/customers?level=high")).json()["total"] == 0
    assert (await loaded.get("/api/v1/customers?search=0003")).json()["items"][0]["id"] == 3
    for bad in ("sort=x", "order=up", "pageSize=0", "page=99999999999999999999", "level=zzz"):
        assert (await loaded.get(f"/api/v1/customers?{bad}")).status_code == 422
    card = (await loaded.get("/api/v1/customers/5")).json()
    assert card["id"] == 5 and len(card["services"]) == 3
    assert (await loaded.get("/api/v1/customers/999")).status_code == 404
    assert (await loaded.get("/api/v1/customers/99999999999999999999")).status_code == 422


async def test_model_settings_patch_bumps_version(loaded: AsyncClient):
    before = (await loaded.get("/api/v1/analytics/summary")).json()["version"]
    patched = await loaded.patch("/api/v1/model/settings", json={"asOf": "2026-10-19T15:00:00Z"})
    assert patched.status_code == 200
    assert patched.json()["version"] == before + 1
    assert (await loaded.patch("/api/v1/model/settings", json={"asOf": "abc"})).status_code == 422
    assert (await loaded.patch("/api/v1/model/settings", json=[1])).status_code == 422


async def test_data_endpoints_require_login(client: AsyncClient):
    for path in ("/api/v1/customers", "/api/v1/customers/1", "/api/v1/analytics/summary", "/api/v1/analytics/churn-trend", "/api/v1/model/settings", "/api/v1/events"):
        assert (await client.get(path)).status_code == 401
    assert (await client.get("/metrics")).status_code == 200


async def test_churn_trend_buckets_and_at_risk_count(loaded: AsyncClient):
    response = await loaded.get("/api/v1/analytics/churn-trend?weeksBack=4&weeksForward=4")
    assert response.status_code == 200
    body = response.json()

    buckets = body["buckets"]
    assert len(buckets) == 9  # 4 назад + текущая + 4 вперёд
    # Периоды идут по порядку без разрывов, по 7 дней каждый
    for b in buckets:
        start = datetime.fromisoformat(b["periodStart"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(b["periodEnd"].replace("Z", "+00:00"))
        assert end - start == timedelta(days=7)
    starts = [b["periodStart"] for b in buckets]
    assert starts == sorted(starts)
    # Прошлые бакеты помечены фактом, начиная с текущей недели — прогнозом
    assert any(not b["isForecast"] for b in buckets)
    assert any(b["isForecast"] for b in buckets)
    forecast_started = False
    for b in buckets:
        if b["isForecast"]:
            forecast_started = True
        else:
            assert not forecast_started, "факт не должен идти после начала прогноза"

    for b in buckets:
        assert b["churnedServices"] <= b["expiredServices"]
        assert b["expiredServices"] >= 0

    assert body["atRiskServices"] >= 0
    assert body["generatedAt"]

    # Некорректные диапазоны отклоняются
    assert (await loaded.get("/api/v1/analytics/churn-trend?weeksBack=0")).status_code == 422
    assert (await loaded.get("/api/v1/analytics/churn-trend?weeksForward=999")).status_code == 422


async def test_refresh_extends_session(admin: AsyncClient, db_session):
    soon = datetime.now(timezone.utc) + timedelta(hours=1)
    await db_session.execute(update(AuthSession).values(expires_at=soon))
    await db_session.commit()
    assert (await admin.post("/api/v1/auth/refresh")).status_code == 200
    expires = (await db_session.execute(select(AuthSession.expires_at))).scalars().first()
    assert expires > datetime.now(timezone.utc) + timedelta(days=29)


async def test_manager_cannot_use_admin_login(admin: AsyncClient, db_session):
    from app.core.security import get_password_hash
    from app.db.models import User

    db_session.add(User(login="admin", email="fake@example.com", password_hash=get_password_hash("Passw0rd-1"), role="manager"))
    await db_session.commit()
    from httpx import ASGITransport, AsyncClient as Client
    async with Client(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        assert (await c.post("/api/v1/auth/login", json={"login": "admin", "password": "Passw0rd-1"})).status_code == 401


def _config(**overrides) -> Config:
    base = dict(
        postgres_user="u", postgres_password="strong-db-pass", postgres_db="d", postgres_host="h",
        jwt_secret_key="a" * 40, jwt_refresh_secret_key="b" * 40, admin_login="admin", admin_password="Str0ng-admin-pass",
        session_secret_key="c" * 40,
    )
    return Config(_env_file=None, **{**base, **overrides})


def test_config_rejects_equal_jwt_secrets():
    with pytest.raises(ValidationError):
        _config(jwt_refresh_secret_key="a" * 40)


def test_config_rejects_example_secrets_only_in_secure_mode():
    _config(admin_password="admin12345")  # локально допустимо (только предупреждение)
    with pytest.raises(ValidationError):
        _config(admin_password="admin12345", cookie_secure=True)
    with pytest.raises(ValidationError):
        _config(jwt_secret_key="change_me_" + "x" * 30, cookie_secure=True)


async def test_delete_model_setting(loaded: AsyncClient, monkeypatch):
    import app.analysis as analysis

    original = analysis.default_settings
    monkeypatch.setattr(analysis, "default_settings", lambda: {**original(), "weights": {"x": 1.0, "y": 2.0}})

    before = (await loaded.get("/api/v1/model/settings")).json()
    assert before["settings"]["weights"] == {"x": 1.0, "y": 2.0}
    version = (await loaded.get("/api/v1/analytics/summary")).json()["version"]

    deleted = await loaded.delete("/api/v1/model/settings/weights/x")
    assert deleted.status_code == 200
    assert deleted.json()["settings"]["weights"] == {"y": 2.0}
    assert deleted.json()["version"] == version + 1
    # Дефолтный пункт не возвращается ни при чтении, ни после других изменений
    assert (await loaded.get("/api/v1/model/settings")).json()["settings"]["weights"] == {"y": 2.0}
    patched = await loaded.patch("/api/v1/model/settings", json={"asOf": "2026-10-19T15:00:00Z"})
    assert patched.json()["settings"]["weights"] == {"y": 2.0}
    # defaults показывают, что было по умолчанию
    assert patched.json()["defaults"]["weights"] == {"x": 1.0, "y": 2.0}

    assert (await loaded.delete("/api/v1/model/settings/weights/x")).status_code == 404
    assert (await loaded.delete("/api/v1/model/settings/nothing/x")).status_code == 404
    assert (await loaded.delete("/api/v1/model/settings/asOf/x")).status_code == 422

    # Снова заданный пункт возвращается и не считается удалённым
    added = await loaded.patch("/api/v1/model/settings", json={"weights": {"x": 5.0}})
    assert added.json()["settings"]["weights"] == {"x": 5.0, "y": 2.0}
    assert (await loaded.get("/api/v1/model/settings")).json()["settings"]["weights"] == {"x": 5.0, "y": 2.0}


async def test_delete_model_setting_requires_admin(client: AsyncClient):
    assert (await client.delete("/api/v1/model/settings/weights/x")).status_code == 401
    assert (await client.post("/api/v1/auth/login", json=ADMIN)).status_code == 200
    created = await client.post("/api/v1/users", json={"login": "mgr1", "email": "mgr1@example.com", "password": "Passw0rd-1"})
    assert created.status_code == 201
    from httpx import ASGITransport, AsyncClient as Client
    async with Client(transport=ASGITransport(app=app), base_url="http://testserver") as m:
        assert (await m.post("/api/v1/auth/login", json={"login": "mgr1", "password": "Passw0rd-1"})).status_code == 200
        assert (await m.delete("/api/v1/model/settings/weights/x")).status_code == 403
