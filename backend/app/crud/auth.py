import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from hmac import compare_digest

from fastapi import Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.engine import SessionLocal
from app.core.security import (
    ACCESS_COOKIE,
    DUMMY_HASH,
    REFRESH_COOKIE,
    access_decode_token,
    create_access_token,
    create_refresh_token,
    get_session_id,
    get_token,
    hash_token,
    refresh_decode_token,
    verify_credentials,
    verify_password,
)
from app.dao.session import SessionsDAO
from app.dao.user import UsersDAO
from app.db.models.sessions import AuthSession
from app.db.schemas.auth import CurrentUser


def set_auth_cookies(response: Response, access_token: str, refresh_token: str | None) -> None:
    """Ставит cookie с токенами; refresh=None — оставить в браузере текущий refresh.

    Общий хелпер для локального логина (routers/auth.py) и колбэка OIDC
    (routers/oidc.py) — обе точки входа должны производить одинаковую сессию.
    """
    settings = get_settings()
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.jwt.access_token_expire_minutes * 60,
    )
    if refresh_token:
        response.set_cookie(
            key=REFRESH_COOKIE,
            value=refresh_token,
            httponly=True,
            samesite="lax",
            secure=settings.cookie_secure,
            max_age=settings.jwt.refresh_token_expire_days * 60 * 60 * 24,
        )


def _new_expires_at() -> datetime:
    """Конец сессии: каждая ротация refresh продлевает её на refresh_token_expire_days"""
    return datetime.now(timezone.utc) + timedelta(days=get_settings().jwt.refresh_token_expire_days)


def _admin_user() -> CurrentUser:
    return CurrentUser(login=get_settings().admin.login, role="superadmin")


async def authenticate(db: AsyncSession, login: str, password: str) -> CurrentUser | None:
    """Главный администратор (из .env) или менеджер из БД; при неверных данных None"""
    if verify_credentials(login, password):
        return _admin_user()
    user = await UsersDAO.find_by_login_or_email(db, login)
    if not user:
        await asyncio.to_thread(verify_password, password, DUMMY_HASH)
        return None
    if not await asyncio.to_thread(verify_password, password, user.password_hash):
        return None
    if user.login == get_settings().admin.login:
        # Менеджер с логином админа не должен получить токен с sub админа
        return None
    return CurrentUser(login=user.login, role=user.role, email=user.email)


SUPERADMIN_UID = "superadmin"
# Отличает «uid не передан» (старый вызов без проверки) от «uid передан и равен None»
_UID_UNSET = object()


async def find_user(login: str, uid=_UID_UNSET) -> CurrentUser | None:
    """Пользователь по логину из токена; менеджер проверяется по БД на каждом запросе (удалённый теряет доступ сразу).

    Если передан uid, он сверяется с текущим пользователем: токен менеджера обязан нести uid, равный
    str(user.id) (удалённый и заново созданный с тем же логином менеджер не подхватит старый токен);
    токен без uid допустим только для суперадмина. Без аргумента uid проверка пропускается.
    """
    if login == get_settings().admin.login:
        if uid is not _UID_UNSET and uid is not None and uid != SUPERADMIN_UID:
            return None
        return _admin_user()
    # Короткая своя сессия: ручка SSE не должна держать соединение с БД всё время потока
    async with SessionLocal() as db:
        user = await UsersDAO.find_one_or_none(db, login=login)
    if not user:
        return None
    if uid is not _UID_UNSET and uid != str(user.id):
        return None
    return CurrentUser(login=user.login, role=user.role, email=user.email)


async def get_current_user(token: str = Depends(get_token)) -> CurrentUser:
    payload = access_decode_token(token)
    user = await find_user(payload.get("sub", ""), payload.get("uid"))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь не найден")
    return user


async def require_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Пускает суперадмина и админов (управление менеджерами, настройки модели, данные), менеджеру 403"""
    if current_user.role not in ("superadmin", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")
    return current_user


async def require_superadmin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Пускает только суперадмина, иначе 403"""
    if current_user.role != "superadmin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")
    return current_user


def _issue_pair(login: str, uid: str, session_id: uuid.UUID) -> tuple[str, str]:
    access_token = create_access_token({"sub": login, "uid": uid})
    refresh_token = create_refresh_token({"sub": login, "uid": uid, "sid": str(session_id)})
    return access_token, refresh_token


async def _resolve_uid(db: AsyncSession, login: str) -> str:
    """uid для токена: суперадмин (.env) -> 'superadmin', менеджер/админ -> str(user.id)"""
    if login == get_settings().admin.login:
        return SUPERADMIN_UID
    user = await UsersDAO.find_one_or_none(db, login=login)
    return str(user.id) if user else SUPERADMIN_UID


async def start_session(db: AsyncSession, login: str) -> tuple[str, str]:
    """Создаёт сессию входа и возвращает пару токенов (access, refresh)"""
    await SessionsDAO.delete_expired(db)
    uid = await _resolve_uid(db, login)
    session_id = uuid.uuid4()
    access_token, refresh_token = _issue_pair(login, uid, session_id)
    expires_at = _new_expires_at()
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

    login = payload.get("sub", "")
    uid = payload.get("uid")
    if not await find_user(login, uid):
        # Менеджера удалили (или заново создали с тем же логином — uid не совпадёт): сессии закрываются
        await SessionsDAO.delete_by_login(db, login)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token не действителен")

    access_token, new_refresh_token = _issue_pair(login, uid or SUPERADMIN_UID, session_id)
    if await SessionsDAO.rotate_refresh_hash(
        db, session_id, token_hash, hash_token(new_refresh_token), _new_expires_at()
    ):
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
