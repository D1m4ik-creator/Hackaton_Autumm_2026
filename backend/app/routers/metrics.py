from fastapi import APIRouter, Response

import app.crud.metrics as crud_metrics
from app.core.engine import SessionDep

router = APIRouter(tags=["metrics"])

# Формат Content-Type, который ждёт Prometheus
METRICS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


@router.get("/metrics")
async def metrics(db: SessionDep) -> Response:
    """Метрики Prometheus: только агрегаты, без входа (скрейпер не носит cookie)"""
    body = await crud_metrics.render_metrics(db)
    return Response(content=body, media_type=METRICS_CONTENT_TYPE)
