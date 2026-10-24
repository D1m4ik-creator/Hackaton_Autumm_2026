from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.engine import SessionLocal
from app.dao.risk_summary import RiskSummaryDAO

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", responses={503: {"description": "База недоступна (status=unavailable)"}})
async def health():
    """Готовность сервиса: база отвечает и видно состояние данных.

    Отдаёт число клиентов и версию последнего пересчёта. Если база недоступна —
    503 без деталей (внутренности наружу не раскрываем). Сессия открывается внутри
    ручки, чтобы поймать и сбой самого соединения.
    """
    try:
        async with SessionLocal() as session:
            summary = await RiskSummaryDAO.get(session)
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return {
        "status": "ok",
        "data": {
            "customers": summary.customers_total if summary else 0,
            "version": summary.version if summary else 0,
        },
    }
