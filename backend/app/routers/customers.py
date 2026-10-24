from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query, Response

import app.crud.auth as crud_auth
import app.crud.customer_export as customer_export
import app.crud.customers as crud_customers
from app.core.engine import ReadSessionDep
from app.core.openapi import error_responses
from app.db.schemas.customers import CustomerCard, CustomerPage

router = APIRouter(
    prefix="/customers",
    tags=["customers"],
    dependencies=[Depends(crud_auth.get_current_user)],
    responses=error_responses(401),
)

Level = Literal["high", "medium", "low", "no_data"]
Sort = Literal["id", "email", "balance", "totalReplenished", "riskScore", "expectedLossCents"]


@router.get("", response_model=CustomerPage)
async def list_customers(
    db: ReadSessionDep,
    level: Annotated[list[Level] | None, Query(description="Фильтр по уровням риска")] = None,
    search: Annotated[str | None, Query(max_length=100, description="Подстрока email; только цифры — ещё и точный id")] = None,
    sort: Sort = "riskScore",
    order: Literal["asc", "desc"] = "desc",
    page: Annotated[int, Query(ge=1, le=1_000_000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200, alias="pageSize")] = 50,
) -> CustomerPage:
    """Список клиентов с фильтром, поиском, сортировкой и пагинацией"""
    return await crud_customers.list_customers(
        db, levels=level, search=search, sort=sort, order=order, page=page, page_size=page_size
    )


# Объявлен до /{customerId}, иначе «export» попадёт в параметр пути
@router.get(
    "/export",
    response_class=Response,
    responses={200: {"content": {media: {} for media in customer_export.MEDIA_TYPES.values()}}},
)
async def export_customers(
    db: ReadSessionDep,
    format: customer_export.ExportFormat = "csv",
    level: Annotated[list[Level] | None, Query(description="Фильтр по уровням риска")] = None,
    search: Annotated[str | None, Query(max_length=100, description="Подстрока email; только цифры — ещё и точный id")] = None,
    sort: Sort = "riskScore",
    order: Literal["asc", "desc"] = "desc",
) -> Response:
    """Выгрузка клиентов в CSV, Excel или JSON с теми же фильтром и сортировкой, что список (без пагинации)"""
    body, filename = await customer_export.export_customers(
        db, fmt=format, levels=level, search=search, sort=sort, order=order
    )
    return Response(
        content=body,
        media_type=customer_export.MEDIA_TYPES[format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{customerId}", response_model=CustomerCard, responses=error_responses(404))
async def get_customer(
    db: ReadSessionDep,
    customer_id: Annotated[int, Path(alias="customerId", ge=1, le=9_223_372_036_854_775_807)],
) -> CustomerCard:
    """Карточка одного клиента"""
    return await crud_customers.get_customer_card(db, customer_id)
