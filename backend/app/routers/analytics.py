from fastapi import APIRouter, Depends

import app.crud.analytics as crud_analytics
import app.crud.auth as crud_auth
from app.core.engine import ReadSessionDep
from app.core.openapi import error_responses
from app.db.schemas.analytics import SummaryOut

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"],
    dependencies=[Depends(crud_auth.get_current_user)],
    responses=error_responses(401),
)


@router.get("/summary", response_model=SummaryOut)
async def summary(db: ReadSessionDep) -> SummaryOut:
    """Сводка по всем клиентам (те же числа, что в /metrics)"""
    return await crud_analytics.get_summary(db)
