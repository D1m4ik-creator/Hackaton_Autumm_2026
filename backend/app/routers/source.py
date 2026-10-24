from fastapi import APIRouter, Depends

import app.crud.auth as crud_auth
import app.crud.recalc as recalc
from app.core.engine import SessionDep
from app.db.schemas.source import SnapshotIn, SnapshotLoadResult

router = APIRouter(
    prefix="/source",
    tags=["source"],
    dependencies=[Depends(crud_auth.require_admin)],
)


@router.put("/snapshot", response_model=SnapshotLoadResult)
async def put_snapshot(db: SessionDep, snapshot: SnapshotIn) -> SnapshotLoadResult:
    """Полная замена исходных данных и пересчёт в одной транзакции"""
    return await recalc.apply_snapshot(db, snapshot)
