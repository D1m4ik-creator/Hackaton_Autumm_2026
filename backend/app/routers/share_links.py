import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path

import app.crud.auth as crud_auth
import app.crud.share_links as crud_share_links
from app.core.engine import SessionDep
from app.core.openapi import error_responses
from app.db.schemas.auth import CurrentUser
from app.db.schemas.share_link import ShareLinkCreatedOut, ShareLinkCreateIn, ShareLinkOut

router = APIRouter(
    prefix="/share-links",
    tags=["share-links"],
    dependencies=[Depends(crud_auth.require_admin)],
    responses=error_responses(401, 403),
)


@router.post("", response_model=ShareLinkCreatedOut)
async def create_share_link(
    db: SessionDep, body: ShareLinkCreateIn, current_user: Annotated[CurrentUser, Depends(crud_auth.require_admin)]
) -> ShareLinkCreatedOut:
    """Создать публичную read-only ссылку на отчёт (только администратор). Токен отдаётся один раз."""
    return await crud_share_links.create_share_link(db, body, current_user)


@router.get("", response_model=list[ShareLinkOut])
async def list_share_links(db: SessionDep) -> list[ShareLinkOut]:
    """Все созданные ссылки (без токенов — хранится только их хэш)"""
    return await crud_share_links.list_share_links(db)


@router.delete("/{linkId}", responses=error_responses(404))
async def revoke_share_link(db: SessionDep, link_id: Annotated[uuid.UUID, Path(alias="linkId")]) -> dict:
    """Отозвать ссылку (не удаляет запись — историю, что ссылка была, видно)"""
    await crud_share_links.revoke_share_link(db, link_id)
    return {"status": "ok"}
