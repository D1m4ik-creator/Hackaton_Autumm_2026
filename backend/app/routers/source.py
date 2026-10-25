from typing import Literal

from fastapi import APIRouter, Depends, Query

import app.crud.auth as crud_auth
import app.crud.recalc as recalc
from app.core.engine import SessionDep
from app.core.openapi import error_responses
from app.db.schemas.source import SnapshotIn, SnapshotLoadResult

router = APIRouter(
    prefix="/source",
    tags=["source"],
    dependencies=[Depends(crud_auth.require_admin)],
    responses=error_responses(401, 403),
)


@router.put("/snapshot", response_model=SnapshotLoadResult, responses=error_responses(413, 503))
async def put_snapshot(
    db: SessionDep,
    snapshot: SnapshotIn,
    mode: Literal["replace", "merge"] = Query(
        "replace",
        description="replace — полная замена данных (по умолчанию); "
        "merge — добавить к существующим, при пересечении id/email — 422, старые данные не трогаются",
    ),
) -> SnapshotLoadResult:
    """Загрузка исходных данных и пересчёт в одной транзакции (замена или добавление)"""
    return await recalc.apply_snapshot(db, snapshot, mode)
