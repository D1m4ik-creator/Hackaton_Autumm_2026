from fastapi import APIRouter
from sqlalchemy import text

from app.core.engine import SessionDep

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health(db: SessionDep):
    """Проверка, что API жив и база отвечает"""
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}
