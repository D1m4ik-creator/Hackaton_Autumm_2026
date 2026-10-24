import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

import app.crud.recalc as crud_recalc
from app.core.config import get_settings
from app.core.engine import SessionLocal, close_engine
from app.core.limiter import limiter
from app.crud.recalc import AnalysisContractError
from app.routers import analytics, auth, customers, events, health, metrics, model_settings, source, users

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Первичная загрузка снимка и пересчёт при старте; при ошибке API всё равно поднимается
    try:
        async with SessionLocal() as session:
            await crud_recalc.startup(session)
    except Exception:
        logger.exception("Первичная загрузка и пересчёт при старте не удались")
    yield
    await close_engine()  # Закрытие движка при завершении работы приложения


API_PREFIX = "/api/v1"

app = FastAPI(
    title="Hackathon API",
    description="Backend для хакатона Autumn 2026",
    lifespan=lifespan,
    docs_url=f"{API_PREFIX}/docs",
    openapi_url=f"{API_PREFIX}/openapi.json",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Слишком много запросов с одного IP -> 429"""
    return JSONResponse(
        status_code=429,
        content={"detail": "Слишком много запросов, попробуйте позже"},
        headers={"Retry-After": "60"},
    )


@app.exception_handler(AnalysisContractError)
async def analysis_contract_error_handler(request: Request, exc: AnalysisContractError) -> JSONResponse:
    """Нарушение контракта модели анализа -> 500 (транзакция уже откачена)"""
    return JSONResponse(status_code=500, content={"detail": f"Ошибка модели анализа: {exc}"})


# /metrics — без префикса и без входа; остальное — под /api/v1 с авторизацией
app.include_router(metrics.router)
app.include_router(health.router, prefix=API_PREFIX)
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(customers.router, prefix=API_PREFIX)
app.include_router(analytics.router, prefix=API_PREFIX)
app.include_router(model_settings.router, prefix=API_PREFIX)
app.include_router(source.router, prefix=API_PREFIX)
app.include_router(events.router, prefix=API_PREFIX)
app.include_router(users.router, prefix=API_PREFIX)
