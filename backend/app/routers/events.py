import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent

import app.crud.auth as crud_auth
from app.core.config import get_settings
from app.core.engine import SessionLocal
from app.core.openapi import error_responses
from app.core.security import access_decode_token, get_token
from app.dao.risk_summary import RiskSummaryDAO
from app.db.models.risk_summary import RiskSummary

USER_RECHECK_SECONDS = 60

router = APIRouter(
    tags=["events"],
    dependencies=[Depends(crud_auth.get_current_user)],
    responses=error_responses(401),
)


def _iso(value: datetime | None) -> str | None:
    """ISO-8601 в UTC с суффиксом Z"""
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _payload(summary: RiskSummary | None, version: int) -> dict:
    """Тело SSE-события в camelCase"""
    return {
        "version": version,
        "reason": summary.reason if summary else "init",
        "recalculatedAt": _iso(summary.recalculated_at if summary else None),
    }


async def _read_summary() -> RiskSummary | None:
    """Короткая сессия на одну итерацию: SSE не держит соединение весь поток"""
    async with SessionLocal() as session:
        return await RiskSummaryDAO.get(session)


@router.get("/events", response_class=EventSourceResponse)
async def events(request: Request) -> AsyncIterator[ServerSentEvent]:
    """Поток обновлений: опрос risk_summary.version, событие recalculated при смене версии"""
    settings = get_settings()
    interval = settings.sse_poll_interval_seconds
    # Поток закрывается, когда истекает access-токен; браузер переподключается
    payload = access_decode_token(get_token(request))
    exp = payload.get("exp", 0)
    login = payload.get("sub", "")
    next_user_check = datetime.now(timezone.utc).timestamp() + USER_RECHECK_SECONDS
    last_event_id = request.headers.get("Last-Event-ID")

    summary = await _read_summary()
    version = summary.version if summary else 0

    # Первое сообщение: подсказка retry, затем ready (или recalculated, если версия ушла вперёд)
    yield ServerSentEvent(retry=3000)
    first_event = "recalculated" if last_event_id is not None and last_event_id != str(version) else "ready"
    yield ServerSentEvent(event=first_event, id=str(version), data=_payload(summary, version))

    last_version = version
    while True:
        if await request.is_disconnected():
            break
        if datetime.now(timezone.utc).timestamp() >= exp:
            break
        if datetime.now(timezone.utc).timestamp() >= next_user_check:
            # Менеджера могли удалить: поток закрывается, переподключение даст 401
            if not await crud_auth.find_user(login):
                break
            next_user_check = datetime.now(timezone.utc).timestamp() + USER_RECHECK_SECONDS
        await asyncio.sleep(interval)
        summary = await _read_summary()
        current = summary.version if summary else 0
        if current != last_version:
            last_version = current
            yield ServerSentEvent(event="recalculated", id=str(current), data=_payload(summary, current))
