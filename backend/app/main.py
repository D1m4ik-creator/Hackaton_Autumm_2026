import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

import app.crud.recalc as crud_recalc
from app.core.config import get_settings
from app.core.engine import SessionLocal, close_engine
from app.core.limiter import limiter
from app.core.oidc_client import register_oidc_client
from app.crud.recalc import AnalysisContractError
from app.routers import analytics, auth, customers, events, health, metrics, model_settings, oidc, source, users

logger = logging.getLogger(__name__)

# Предел размера тела запроса: больше -> 413, тело дальше не читаем (25 МиБ)
MAX_BODY_BYTES = 25 * 1024 * 1024


class BodySizeLimitMiddleware:
    """Ограничивает размер тела запроса (чистый ASGI).

    Есть Content-Length больше предела — сразу 413, тело не читаем. Без
    Content-Length (chunked) считаем прочитанные байты и при превышении отвечаем
    413, не передавая запрос приложению. Приложение само не может ответить 413
    из чтения тела: FastAPI превращает ошибку чтения в 400, поэтому решаем здесь.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        limit = MAX_BODY_BYTES
        content_length = Headers(scope=scope).get("content-length")
        if content_length is not None:
            try:
                declared = int(content_length)
            except ValueError:
                declared = None
            if declared is not None and declared > limit:
                await self._reject(scope, receive, send)
                return
            # Content-Length в пределах: доверяем ему, тело не буферизуем
            await self.app(scope, receive, send)
            return

        # Chunked: Content-Length нет — буферизуем и считаем, обрываем при превышении
        buffered: list[Message] = []
        total = 0
        more_body = True
        while more_body:
            message = await receive()
            if message["type"] != "http.request":
                buffered.append(message)
                break
            total += len(message.get("body", b""))
            if total > limit:
                await self._reject(scope, receive, send)
                return
            buffered.append(message)
            more_body = message.get("more_body", False)

        iterator = iter(buffered)

        async def replay() -> Message:
            try:
                return next(iterator)
            except StopIteration:
                return await receive()

        await self.app(scope, replay, send)

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send) -> None:
        response = JSONResponse(status_code=413, content={"detail": "Слишком большой запрос"})
        await response(scope, receive, send)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Регистрация OIDC-клиента (authlib) против Authentik — только если включено:
    # с пустыми OIDC_ISSUER/CLIENT_ID регистрировать нечего, /auth/oidc/* и так
    # отвечают 404 через oidc_enabled-чек в самом роутере
    if get_settings().oidc_enabled:
        register_oidc_client()
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

# Порядок важен: Starlette выполняет middleware в обратном порядке добавления
# (добавленный последним срабатывает первым на входящий запрос) — CORS должен
# отработать раньше, чем запрос дойдёт до SessionMiddleware/роутов
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Внешний слой: ограничение размера тела должно сработать раньше разбора запроса
app.add_middleware(BodySizeLimitMiddleware)

# Нужен authlib (routers/oidc.py) — между редиректом на Authentik и колбэком
# state/PKCE-verifier хранятся в request.session, а не в cookie с токенами
app.add_middleware(
    SessionMiddleware,
    secret_key=get_settings().session_secret_key.get_secret_value(),
    same_site="lax",
    https_only=get_settings().cookie_secure,
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
app.include_router(oidc.router, prefix=API_PREFIX)
