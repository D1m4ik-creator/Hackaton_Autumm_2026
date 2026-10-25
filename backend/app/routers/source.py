from typing import Annotated, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

import app.crud.auth as crud_auth
import app.crud.recalc as recalc
from app.crud.snapshot_files import SnapshotFormat, parse_snapshot_file
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


@router.put("/snapshot/file", response_model=SnapshotLoadResult, responses=error_responses(413, 503))
async def put_snapshot_file(
    db: SessionDep,
    content: Annotated[bytes, Body(media_type="application/octet-stream")],
    format: Annotated[SnapshotFormat, Query(description="Формат файла снимка: json, csv или xlsx")],
    mode: Literal["replace", "merge"] = "replace",
) -> SnapshotLoadResult:
    """Загрузка файла снимка из JSON, CSV или Excel с теми же проверками и пересчётом."""
    try:
        snapshot = await run_in_threadpool(parse_snapshot_file, content, format)
    except ValidationError as exc:
        raise RequestValidationError([
            {**error, "loc": ("body", *error["loc"])}
            for error in exc.errors(include_url=False)[:50]
        ]) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return await recalc.apply_snapshot(db, snapshot, mode)
