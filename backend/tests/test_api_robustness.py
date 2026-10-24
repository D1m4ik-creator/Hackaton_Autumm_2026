"""Устойчивость API: лимит тела (413), 503 при занятой блокировке, лимиты списков,
согласованное чтение (REPEATABLE READ), готовность /health, согласованность /metrics и SSE.
"""

import json
from pathlib import Path

import anyio
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text, update

import app.crud.recalc as recalc
import app.main as main_module
from app.core.engine import SessionLocal, get_read_session
from app.db.models import RiskSummary
from app.db.schemas.source import MAX_ACCOUNTS, MAX_SERVICES, MAX_TRANSACTIONS, SnapshotIn
from app.main import app

SNAPSHOT = json.loads(
    (Path(__file__).resolve().parents[2] / "origin_data" / "data.json").read_text(encoding="utf-8")
)
ADMIN = {"login": "admin", "password": "test_password"}


@pytest.fixture
async def admin(client: AsyncClient) -> AsyncClient:
    assert (await client.post("/api/v1/auth/login", json=ADMIN)).status_code == 200
    return client


@pytest.fixture
async def loaded(admin: AsyncClient) -> AsyncClient:
    assert (await admin.put("/api/v1/source/snapshot", json=SNAPSHOT)).status_code == 200
    return admin


# --- Задача 3: ограничение размера тела ---------------------------------------


async def test_body_too_large_by_content_length(admin: AsyncClient, monkeypatch):
    """Content-Length больше предела -> 413, тело не читается"""
    monkeypatch.setattr(main_module, "MAX_BODY_BYTES", 100)
    body = {"accounts": [], "services": [], "transactions": [], "pad": "x" * 500}
    response = await admin.put("/api/v1/source/snapshot", json=body)
    assert response.status_code == 413
    assert response.json()["detail"] == "Слишком большой запрос"


async def test_body_too_large_chunked(admin: AsyncClient, monkeypatch):
    """Поток без Content-Length обрывается при превышении -> 413"""
    monkeypatch.setattr(main_module, "MAX_BODY_BYTES", 100)

    async def stream():
        yield b"x" * 300

    response = await admin.put("/api/v1/source/snapshot", content=stream())
    assert response.status_code == 413
    assert response.json()["detail"] == "Слишком большой запрос"


async def test_body_within_limit_passes(admin: AsyncClient):
    """Нормальный снимок не режется лимитом тела"""
    assert (await admin.put("/api/v1/source/snapshot", json=SNAPSHOT)).status_code == 200


# --- Задача 3: лимиты размеров списков снимка ---------------------------------


def test_snapshot_list_limits_in_schema():
    schema = SnapshotIn.model_json_schema()["properties"]
    assert schema["accounts"]["maxItems"] == MAX_ACCOUNTS
    assert schema["services"]["maxItems"] == MAX_SERVICES
    assert schema["transactions"]["maxItems"] == MAX_TRANSACTIONS


def test_accounts_over_limit_rejected():
    """Список длиннее лимита -> ошибка валидации (на уровне API это 422)"""
    acc = {
        "id": 1,
        "email": "a",
        "balance": 0,
        "withdrawBalance": 0,
        "totalReplenished": 0,
        "bonusBalance": 0,
        "bonusState": "locked",
    }
    data = {"accounts": [acc] * (MAX_ACCOUNTS + 1), "services": [], "transactions": []}
    with pytest.raises(Exception) as info:
        SnapshotIn.model_validate(data)
    assert "too_long" in str(info.value)


async def test_oversized_accounts_list_returns_422(admin: AsyncClient):
    """Тот же лимит через HTTP: длинный список -> 422, а не 500"""
    acc = {
        "id": 1,
        "email": "a",
        "balance": 0,
        "withdrawBalance": 0,
        "totalReplenished": 0,
        "bonusBalance": 0,
        "bonusState": "locked",
    }
    body = {"accounts": [acc] * (MAX_ACCOUNTS + 1), "services": [], "transactions": []}
    assert (await admin.put("/api/v1/source/snapshot", json=body)).status_code == 422


# --- Задача 2: 503 при занятой блокировке пересчёта ---------------------------


async def test_patch_settings_returns_503_when_lock_held(admin: AsyncClient, monkeypatch):
    """Если advisory-lock держит другой пересчёт, PATCH отдаёт 503 с Retry-After"""
    monkeypatch.setattr(recalc, "LOCK_TIMEOUT_MS", 300)

    holder = SessionLocal()
    await holder.execute(
        text("SELECT pg_advisory_xact_lock(:key)"), {"key": recalc.RECALC_LOCK_KEY}
    )
    try:
        with anyio.fail_after(20):
            response = await admin.patch(
                "/api/v1/model/settings", json={"asOf": "2026-10-19T15:00:00Z"}
            )
        assert response.status_code == 503
        assert response.json()["detail"] == "Идёт пересчёт данных, повторите запрос позже"
        assert response.headers.get("Retry-After")
    finally:
        await holder.rollback()
        await holder.close()


async def test_lock_released_allows_next_request(admin: AsyncClient):
    """После освобождения блокировки запросы снова проходят"""
    assert (
        await admin.patch("/api/v1/model/settings", json={"asOf": "2026-10-19T15:00:00Z"})
    ).status_code == 200


# --- Задача 1: согласованное чтение (REPEATABLE READ, read only) --------------


async def test_read_session_is_repeatable_read_readonly():
    gen = get_read_session()
    session = await gen.__anext__()
    try:
        iso = (await session.execute(text("SHOW transaction_isolation"))).scalar_one()
        readonly = (await session.execute(text("SHOW transaction_read_only"))).scalar_one()
        assert iso == "repeatable read"
        assert readonly == "on"
    finally:
        await gen.aclose()


async def test_read_session_sees_single_snapshot(loaded: AsyncClient):
    """Внутри одного чтения смена версии другим коммитом не видна (нет смешения версий)"""
    gen = get_read_session()
    session = await gen.__anext__()
    try:
        first = (await session.execute(select(RiskSummary.version))).scalar_one()
        async with SessionLocal() as other:
            await other.execute(
                update(RiskSummary).where(RiskSummary.id == 1).values(version=RiskSummary.version + 1)
            )
            await other.commit()
        second = (await session.execute(select(RiskSummary.version))).scalar_one()
        assert first == second
    finally:
        await gen.aclose()

    # Новое чтение уже видит новую версию
    gen2 = get_read_session()
    session2 = await gen2.__anext__()
    try:
        fresh = (await session2.execute(select(RiskSummary.version))).scalar_one()
        assert fresh == first + 1
    finally:
        await gen2.aclose()


# --- Задача 5: готовность /health и согласованность /metrics ------------------


async def test_health_reports_data_readiness(loaded: AsyncClient):
    response = await loaded.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["data"]["customers"] == 10
    assert body["data"]["version"] >= 1


async def test_health_503_when_db_unavailable(client: AsyncClient, monkeypatch):
    async def boom(session):
        raise RuntimeError("db unreachable secret internals")

    monkeypatch.setattr("app.dao.risk_summary.RiskSummaryDAO.get", boom)
    response = await client.get("/api/v1/health")
    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"
    assert "secret internals" not in response.text


async def test_metrics_consistent_with_summary(loaded: AsyncClient):
    summary = (await loaded.get("/api/v1/analytics/summary")).json()
    metrics = (await loaded.get("/metrics")).text
    assert "# HELP churn_customers" in metrics
    assert "# TYPE churn_customers gauge" in metrics
    assert f"churn_recalculations_total {summary['version']}" in metrics

    per_level_total = sum(
        int(line.split()[-1])
        for line in metrics.splitlines()
        if line.startswith("churn_customers{")
    )
    assert per_level_total == summary["customersTotal"]


# --- Задача 6: SSE отдаёт первое событие и завершается при отключении ----------


class _FakeRequest:
    """Минимальный Request для прямого прогона генератора SSE (без ASGITransport,
    который буферизует бесконечный поток)."""

    def __init__(self, token: str, disconnect_after: int = 0):
        self.cookies = {"users_access_token": token}
        self.headers: dict = {}
        self._checks = 0
        self._disconnect_after = disconnect_after

    async def is_disconnected(self) -> bool:
        # Через disconnect_after проверок считаем клиента отключившимся
        result = self._checks >= self._disconnect_after
        self._checks += 1
        return result


async def test_events_yields_ready_then_stops_on_disconnect():
    from app.core.security import create_access_token
    from app.routers.events import events

    token = create_access_token({"sub": "admin"})
    gen = events(_FakeRequest(token, disconnect_after=0))

    with anyio.fail_after(10):
        collected = [event async for event in gen]

    # Генератор завершился сам (отключение клиента), не завис -> утечки соединения нет
    assert any(getattr(event, "event", None) == "ready" for event in collected)
