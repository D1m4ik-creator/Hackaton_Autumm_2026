"""Регрессии по ревью бэкенда: гонки с переиспользованием логина, OIDC email_verified,
CORS на 413, пустые веса модели, удалённые услуги в прогнозе, поиск по 19-значному ID.
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update

import app.crud.auth as crud_auth
import app.main as main_module
import app.routers.oidc as oidc_router
from app.analysis import analyze, default_settings, validate_settings
from app.core.config import get_settings
from app.core.engine import SessionLocal
from app.core.security import ACCESS_COOKIE
from app.db.models import User
from app.main import app
from tests.test_analysis_adapter import AS_OF, _load_source

SNAPSHOT = json.loads(
    (Path(__file__).resolve().parents[2] / "origin_data" / "data.json").read_text(encoding="utf-8")
)
ADMIN = {"login": "admin", "password": "test_password"}
MANAGER = {"login": "manager1", "email": "manager1@example.com", "password": "Passw0rd-1"}
BIGINT_MAX = 2**63 - 1


def _new_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def _login(client: AsyncClient, login: str, password: str) -> int:
    return (await client.post("/api/v1/auth/login", json={"login": login, "password": password})).status_code


@pytest.fixture
async def admin(client: AsyncClient) -> AsyncClient:
    assert await _login(client, ADMIN["login"], ADMIN["password"]) == 200
    return client


async def _create(admin: AsyncClient, **overrides) -> str:
    created = await admin.post("/api/v1/users", json={**MANAGER, **overrides})
    assert created.status_code == 201
    return created.json()["id"]


# --- Сессии и переиспользование логина ------------------------------------------


async def test_session_bound_to_checked_account_not_new_login_owner(admin: AsyncClient):
    """Пароль проверили у менеджера, логин пересоздали админом — токен не даёт доступ новому аккаунту"""
    old_id = await _create(admin)
    async with SessionLocal() as db:
        checked = await crud_auth.authenticate(db, MANAGER["login"], MANAGER["password"])
    assert checked is not None and checked.uid == old_id

    assert (await admin.delete(f"/api/v1/users/{old_id}")).status_code == 204
    await _create(admin, email="other@example.com", password="Other-Passw0rd", role="admin")

    async with SessionLocal() as db:
        access_token, _ = await crud_auth.start_session(db, checked.login, checked.uid)
    async with _new_client() as c:
        c.cookies.set(ACCESS_COOKIE, access_token)
        assert (await c.get("/api/v1/auth/me")).status_code == 401


async def test_stale_refresh_does_not_close_new_owner_sessions(admin: AsyncClient):
    """Refresh удалённого менеджера отвергается, но сессии нового владельца логина живы"""
    old_id = await _create(admin)
    async with _new_client() as old, _new_client() as new:
        assert await _login(old, MANAGER["login"], MANAGER["password"]) == 200
        assert (await admin.delete(f"/api/v1/users/{old_id}")).status_code == 204
        await _create(admin)
        assert await _login(new, MANAGER["login"], MANAGER["password"]) == 200

        assert (await old.post("/api/v1/auth/refresh")).status_code == 401
        assert (await new.post("/api/v1/auth/refresh")).status_code == 200


async def test_password_change_closes_sessions_of_concurrently_renamed_login(admin: AsyncClient, monkeypatch):
    """Пока хэшируется новый пароль, логин переименовали и вошли под новым — эта сессия тоже закрывается"""
    user_id = await _create(admin)
    original_to_thread = asyncio.to_thread
    raced = False
    renamed = _new_client()

    async def racing_to_thread(func, *args, **kwargs):
        nonlocal raced
        if not raced:
            raced = True
            async with SessionLocal() as db:
                await db.execute(update(User).where(User.login == MANAGER["login"]).values(login="renamed1"))
                await db.commit()
            assert await _login(renamed, "renamed1", MANAGER["password"]) == 200
        return await original_to_thread(func, *args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", racing_to_thread)
    async with renamed:
        response = await admin.patch(f"/api/v1/users/{user_id}", json={"password": "New-Passw0rd-1"})
        assert response.status_code == 200
        assert raced
        assert (await renamed.post("/api/v1/auth/refresh")).status_code == 401


# --- OIDC ------------------------------------------------------------------------


class _FakeOidcClient:
    def __init__(self, userinfo: dict):
        self.userinfo = userinfo

    async def authorize_access_token(self, request):
        return {"userinfo": self.userinfo}


@pytest.mark.parametrize(
    ("email_verified", "linked"),
    [(True, True), (False, False), (None, False), ("true", False)],
)
async def test_oidc_links_only_verified_email(admin: AsyncClient, monkeypatch, email_verified, linked):
    await _create(admin)
    userinfo = {"email": MANAGER["email"].upper()}
    if email_verified is not None:
        userinfo["email_verified"] = email_verified
    monkeypatch.setattr(get_settings(), "oidc_enabled", True)
    monkeypatch.setattr(oidc_router.oauth, "create_client", lambda name: _FakeOidcClient(userinfo))

    async with _new_client() as c:
        response = await c.get("/api/v1/auth/oidc/callback", follow_redirects=False)
        assert response.status_code == 302
        assert ("error=oidc_no_account" in response.headers["location"]) is not linked
        assert (ACCESS_COOKIE in response.cookies) is linked


class _UnavailableOidcClient:
    async def authorize_redirect(self, request, redirect_uri):
        raise httpx.HTTPStatusError("404", request=httpx.Request("GET", "http://authentik"), response=httpx.Response(404))


async def test_oidc_login_redirects_when_authentik_unavailable(client: AsyncClient, monkeypatch):
    """Authentik не настроен или ещё стартует: не 500, а возврат на экран входа с понятной ошибкой"""
    monkeypatch.setattr(get_settings(), "oidc_enabled", True)
    monkeypatch.setattr(oidc_router.oauth, "create_client", lambda name: _UnavailableOidcClient())
    response = await client.get("/api/v1/auth/oidc/login", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"].endswith("/login?error=oidc_unavailable")


# --- Лимит тела и CORS -----------------------------------------------------------


async def test_body_too_large_keeps_cors_headers(admin: AsyncClient, monkeypatch):
    """413 должен дойти до браузера с Access-Control-Allow-Origin, иначе фронт видит ошибку сети"""
    monkeypatch.setattr(main_module, "MAX_BODY_BYTES", 100)
    origin = get_settings().cors_origins_list[0]
    response = await admin.put(
        "/api/v1/source/snapshot",
        json={"accounts": [], "pad": "x" * 500},
        headers={"Origin": origin},
    )
    assert response.status_code == 413
    assert response.headers.get("access-control-allow-origin") == origin


# --- Модель и аналитика ----------------------------------------------------------


def test_empty_weights_score_by_bias_only() -> None:
    """weights={} — все признаки удалены: у всех оценённых клиентов одинаковый score только от bias"""
    source = _load_source()
    no_weights = validate_settings({**default_settings(), "weights": {}})
    scores = {c.score for c in analyze(source, no_weights, AS_OF).customers if c.score is not None}
    default_scores = {c.score for c in analyze(source, default_settings(), AS_OF).customers if c.score is not None}
    assert len(scores) == 1
    assert scores != default_scores


async def test_deleted_services_not_in_churn_forecast(admin: AsyncClient):
    """Удалённые услуги с будущим сроком не дают «предстоящих непродлений»"""
    snapshot = json.loads(json.dumps(SNAPSHOT))
    future = (datetime.now(timezone.utc) + timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    for service in snapshot["services"]:
        service["status"] = "deleted"
        service["expiresAt"] = future
    assert (await admin.put("/api/v1/source/snapshot", json=snapshot)).status_code == 200

    body = (await admin.get("/api/v1/analytics/churn-trend?weeksBack=1&weeksForward=4")).json()
    forecast = [b for b in body["buckets"] if b["isForecast"]]
    assert forecast
    assert all(b["expiredServices"] == 0 and b["churnedServices"] == 0 for b in forecast)
    assert body["atRiskServices"] == 0


async def test_search_finds_19_digit_bigint_id(admin: AsyncClient):
    snapshot = json.loads(json.dumps(SNAPSHOT))
    snapshot["accounts"][0]["id"] = BIGINT_MAX
    for service in snapshot["services"]:
        if service["ownerId"] == 1:
            service["ownerId"] = BIGINT_MAX
    assert (await admin.put("/api/v1/source/snapshot", json=snapshot)).status_code == 200

    found = (await admin.get(f"/api/v1/customers?search={BIGINT_MAX}")).json()["items"]
    assert [c["id"] for c in found] == [BIGINT_MAX]
    # За пределами BIGINT — просто поиск по email, без ошибки
    assert (await admin.get(f"/api/v1/customers?search={BIGINT_MAX + 1}")).status_code == 200
