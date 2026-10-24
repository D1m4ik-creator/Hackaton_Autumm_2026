from authlib.integrations.starlette_client import OAuthError
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse

import app.crud.auth as crud_auth
from app.core.config import get_settings
from app.core.engine import SessionDep
from app.core.oidc_client import OIDC_CLIENT_NAME, oauth
from app.dao.user import UsersDAO

router = APIRouter(prefix="/auth/oidc", tags=["auth"])


def _require_enabled() -> None:
    if not get_settings().oidc_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Вход через OIDC не настроен")


@router.get("/status")
async def oidc_status():
    """Фронт дёргает это, чтобы не рисовать кнопку входа через Authentik, если он не настроен"""
    return {"enabled": get_settings().oidc_enabled}


@router.get("/login")
async def login(request: Request):
    _require_enabled()
    client = oauth.create_client(OIDC_CLIENT_NAME)
    return await client.authorize_redirect(request, get_settings().oidc_redirect_uri)


@router.get("/callback")
async def callback(request: Request, db: SessionDep):
    """
    Вход через Authentik даёт доступ только существующему локальному аккаунту
    (admin/manager, созданному через панель «Управление пользователями») —
    сопоставляем по email. Нет совпадения — понятная ошибка на фронте,
    автосоздание аккаунтов не делаем: роль остаётся авторитетной в нашей БД.
    """
    _require_enabled()
    settings = get_settings()
    client = oauth.create_client(OIDC_CLIENT_NAME)

    try:
        token = await client.authorize_access_token(request)
    except OAuthError:
        return RedirectResponse(f"{settings.frontend_url}/login?error=oidc_failed", status_code=status.HTTP_302_FOUND)

    userinfo = token.get("userinfo") or {}
    email = (userinfo.get("email") or "").strip().lower()
    # Неподтверждённую почту IdP может разрешить вписать любую — по ней аккаунты не связываем
    if userinfo.get("email_verified") is not True:
        email = ""
    user = await UsersDAO.find_one_or_none(db, email=email) if email else None
    if not user or user.role not in ("admin", "manager"):
        return RedirectResponse(f"{settings.frontend_url}/login?error=oidc_no_account", status_code=status.HTTP_302_FOUND)

    access_token, refresh_token = await crud_auth.start_session(db, user.login, str(user.id))
    redirect = RedirectResponse(settings.frontend_url, status_code=status.HTTP_302_FOUND)
    crud_auth.set_auth_cookies(redirect, access_token, refresh_token)
    return redirect
