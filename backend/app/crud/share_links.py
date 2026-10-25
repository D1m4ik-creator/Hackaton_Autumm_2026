import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import ReadSessionDep
from app.core.security import generate_share_token, hash_token
from app.dao.share_link import ShareLinkDAO
from app.db.models.share_link import ShareLink
from app.db.schemas.auth import CurrentUser
from app.db.schemas.share_link import ShareLinkCreatedOut, ShareLinkCreateIn, ShareLinkOut


def _is_active(link: ShareLink, now: datetime) -> bool:
    return link.revoked_at is None and link.expires_at > now


def _to_out(link: ShareLink, now: datetime) -> ShareLinkOut:
    return ShareLinkOut(
        id=link.id, label=link.label, created_by_login=link.created_by_login,
        created_at=link.created_at, expires_at=link.expires_at, revoked_at=link.revoked_at,
        active=_is_active(link, now),
    )


async def create_share_link(session: AsyncSession, body: ShareLinkCreateIn, actor: CurrentUser) -> ShareLinkCreatedOut:
    """Создаёт публичную ссылку; сырой токен возвращается только здесь, в БД — только его hash"""
    token = generate_share_token()
    now = datetime.now(timezone.utc)
    link = ShareLink(
        id=uuid.uuid4(), token_hash=hash_token(token), label=body.label,
        created_by_login=actor.login, expires_at=now + timedelta(days=body.expires_in_days),
    )
    session.add(link)
    await session.commit()
    await session.refresh(link)
    out = _to_out(link, now)
    return ShareLinkCreatedOut(**out.model_dump(), token=token)


async def list_share_links(session: AsyncSession) -> list[ShareLinkOut]:
    """Все созданные ссылки, новые сверху — без токенов (хранится только hash)"""
    result = await session.execute(select(ShareLink).order_by(ShareLink.created_at.desc()))
    now = datetime.now(timezone.utc)
    return [_to_out(link, now) for link in result.scalars().all()]


async def revoke_share_link(session: AsyncSession, link_id: uuid.UUID) -> None:
    """Отзывает ссылку (не удаляет строку — история, что ссылка была, остаётся)"""
    link = await ShareLinkDAO.find_by_id(session, link_id)
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ссылка не найдена")
    if link.revoked_at is None:
        await ShareLinkDAO.update_by_id(session, link_id, revoked_at=datetime.now(timezone.utc))


async def require_share_link(
    db: ReadSessionDep, token: str = Query(..., description="Токен из публичной ссылки"),
) -> None:
    """Зависимость публичных ручек (app/routers/public_report.py): валидный, не отозванный и
    не просроченный токен — иначе 401. Не резолвит пользователя: публичные ручки ничего не знают про логин."""
    result = await db.execute(select(ShareLink).where(ShareLink.token_hash == hash_token(token)))
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Ссылка недействительна")
    if not _is_active(link, datetime.now(timezone.utc)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Ссылка отозвана или истекла")
