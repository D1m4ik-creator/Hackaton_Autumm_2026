from typing import Annotated

from fastapi import APIRouter, Depends, Query

import app.crud.analytics as crud_analytics
import app.crud.auth as crud_auth
from app.core.engine import ReadSessionDep
from app.core.openapi import error_responses
from app.db.schemas.analytics import ChurnTrendOut, SummaryOut

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


@router.get("/churn-trend", response_model=ChurnTrendOut)
async def churn_trend(
    db: ReadSessionDep,
    weeks_back: Annotated[int, Query(ge=1, le=52, alias="weeksBack")] = 8,
    weeks_forward: Annotated[int, Query(ge=1, le=52, alias="weeksForward")] = 8,
) -> ChurnTrendOut:
    """График оттока по неделям: факт непродлений, прогноз и число услуг под риском"""
    return await crud_analytics.get_churn_trend(db, weeks_back=weeks_back, weeks_forward=weeks_forward)
