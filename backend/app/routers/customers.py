from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query

import app.crud.auth as crud_auth
import app.crud.customers as crud_customers
from app.core.engine import SessionDep
from app.db.schemas.customers import CustomerCard, CustomerPage

router = APIRouter(
    prefix="/customers",
    tags=["customers"],
    dependencies=[Depends(crud_auth.get_current_user)],
)

Level = Literal["high", "medium", "low", "no_data"]
Sort = Literal["id", "email", "balance", "totalReplenished", "riskScore", "expectedLossCents"]


@router.get("", response_model=CustomerPage)
async def list_customers(
    db: SessionDep,
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


@router.get("/{customerId}", response_model=CustomerCard)
async def get_customer(
    db: SessionDep,
    customer_id: Annotated[int, Path(alias="customerId", ge=1, le=9_223_372_036_854_775_807)],
) -> CustomerCard:
    """Карточка одного клиента"""
    return await crud_customers.get_customer_card(db, customer_id)
