from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query, Request

import app.crud.public_report as crud_public_report
from app.core.engine import ReadSessionDep
from app.core.limiter import limiter, public_report_limit
from app.core.openapi import error_responses
from app.crud.share_links import require_share_link
from app.db.schemas.analytics import SummaryOut
from app.db.schemas.public_report import PublicCustomerCard, PublicCustomerPage

router = APIRouter(
    prefix="/public/report",
    tags=["public-report"],
    dependencies=[Depends(require_share_link)],
    responses=error_responses(401, 429),
)

Level = Literal["high", "medium", "low", "no_data"]
Sort = Literal["id", "balance", "totalReplenished", "riskScore", "expectedLossCents"]


@router.get("/summary", response_model=SummaryOut)
@limiter.limit(public_report_limit)
async def get_public_summary(request: Request, db: ReadSessionDep) -> SummaryOut:
    """Сводка по риску/потерям — публичная, без логина (см. ops/README.md)"""
    return await crud_public_report.get_summary(db)


@router.get("/customers", response_model=PublicCustomerPage)
@limiter.limit(public_report_limit)
async def list_public_customers(
    request: Request,
    db: ReadSessionDep,
    level: Annotated[list[Level] | None, Query(description="Фильтр по уровням риска")] = None,
    search: Annotated[str | None, Query(max_length=100, description="Только цифры — точный id (email скрыт)")] = None,
    sort: Sort = "riskScore",
    order: Literal["asc", "desc"] = "desc",
    page: Annotated[int, Query(ge=1, le=1_000_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200, alias="pageSize")] = 50,
) -> PublicCustomerPage:
    """Список клиентов без email — публичная read-only версия GET /customers"""
    return await crud_public_report.list_customers(
        db, levels=level, search=search, sort=sort, order=order, page=page, page_size=page_size
    )


@router.get("/customers/{customerId}", response_model=PublicCustomerCard, responses=error_responses(404))
@limiter.limit(public_report_limit)
async def get_public_customer(
    request: Request,
    db: ReadSessionDep,
    customer_id: Annotated[int, Path(alias="customerId", ge=1, le=9_223_372_036_854_775_807)],
) -> PublicCustomerCard:
    """Карточка клиента без email — публичная read-only версия GET /customers/{id}"""
    return await crud_public_report.get_customer_card(db, customer_id)
