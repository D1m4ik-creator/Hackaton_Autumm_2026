import uuid
from datetime import datetime, timedelta, timezone
from hmac import compare_digest

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    access_decode_token,
    create_access_token,
    create_refresh_token,
    get_session_id,
    get_token,
    hash_token,
    refresh_decode_token,
    verify_credentials,
)
from app.dao.session import SessionsDAO
from app.db.models.sessions import AuthSession
from app.db.schemas.auth import CurrentUser


def authenticate(login: str, password: str) -> CurrentUser | None:
    """Пользователь, если логин и пароль совпали с учётной записью из .env, иначе None"""
    if not verify_credentials(login, password):
        return None
    return CurrentUser(login=login)


async def get_current_user(token: str = Depends(get_token)) -> CurrentUser:
    payload = access_decode_token(token)
    login = payload.get("sub")
    if login != get_settings().admin.login:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь не найден")
    return CurrentUser(login=login)


def _issue_pair(login: str, session_id: uuid.UUID) -> tuple[str, str]:
    access_token = create_access_token({"sub": login})
    refresh_token = create_refresh_token({"sub": login, "sid": str(session_id)})
    return access_token, refresh_token


async def start_session(db: AsyncSession, login: str) -> tuple[str, str]:
    """Создаёт сессию входа и возвращает пару токенов (access, refresh)"""
    await SessionsDAO.delete_expired(db)
    session_id = uuid.uuid4()
    access_token, refresh_token = _issue_pair(login, session_id)
    expires_at = datetime.now(timezone.utc) + timedelta(days=get_settings().jwt.refresh_token_expire_days)
    await SessionsDAO.add(
        db, id=session_id, login=login, refresh_token_hash=hash_token(refresh_token), expires_at=expires_at
    )
    return access_token, refresh_token


def _is_recent_rotation(auth_session: AuthSession, token_hash: str) -> bool:
    """Токен заменили только что: это параллельный запрос из того же браузера"""
    if not auth_session.previous_token_hash or not auth_session.rotated_at:
        return False
    grace = timedelta(seconds=get_settings().jwt.refresh_grace_seconds)
    return (
        compare_digest(auth_session.previous_token_hash, token_hash)
        and datetime.now(timezone.utc) - auth_session.rotated_at <= grace
    )


async def rotate_session(db: AsyncSession, refresh_token: str | None) -> tuple[str, str | None]:
    """
    Проверяет refresh токен по хэшу в БД и выдаёт новую пару; старый refresh больше не действует.
    Если тот же токен пришёл параллельно сразу после замены, отдаёт только access (refresh уже выдан первому запросу).
    """
    payload = refresh_decode_token(refresh_token)
    session_id = get_session_id(payload)
    token_hash = hash_token(refresh_token)

    access_token, new_refresh_token = _issue_pair(payload.get("sub", ""), session_id)
    if await SessionsDAO.rotate_refresh_hash(db, session_id, token_hash, hash_token(new_refresh_token)):
        return access_token, new_refresh_token

    auth_session = await SessionsDAO.find_by_id(db, session_id)
    if auth_session and _is_recent_rotation(auth_session, token_hash):
        return access_token, None

    if auth_session:
        # Пришёл давно заменённый refresh (возможно украденный): закрываем сессию целиком
        await SessionsDAO.delete_by_id(db, auth_session.id)
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token не действителен")


async def end_session(db: AsyncSession, refresh_token: str | None) -> None:
    """Удаляет сессию по refresh токену; битый или просроченный токен просто игнорируется"""
    try:
        session_id = get_session_id(refresh_decode_token(refresh_token))
    except HTTPException:
        return
    await SessionsDAO.delete_by_id(db, session_id)
