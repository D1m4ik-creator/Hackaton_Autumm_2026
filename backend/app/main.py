from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.engine import close_engine
from app.routers import auth, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Выполнение при старте приложения 
    yield 
    await close_engine() # Закрытие движка при завершении работы приложения


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

app.include_router(health.router, prefix=API_PREFIX)
app.include_router(auth.router, prefix=API_PREFIX)
