from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

import app.crud.auth as crud_auth
from app.core.limiter import limiter, login_limit, refresh_limit
from app.core.config import get_settings
from app.core.engine import SessionDep
from app.core.security import ACCESS_COOKIE, REFRESH_COOKIE
from app.db.schemas.auth import CurrentUser, UserLogin

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str | None) -> None:
    """Ставит cookie с токенами; refresh=None — оставить в браузере текущий refresh"""
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


@router.post("/login")
@limiter.limit(login_limit)
async def login(request: Request, db: SessionDep, user_data: UserLogin, response: Response):
    user = crud_auth.authenticate(user_data.login, user_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")

    access_token, refresh_token = await crud_auth.start_session(db, user.login)
    _set_auth_cookies(response, access_token, refresh_token)
    return {"message": "Успешная авторизация"}


@router.post("/refresh")
@limiter.limit(refresh_limit)
async def refresh(request: Request, db: SessionDep, response: Response):
    access_token, refresh_token = await crud_auth.rotate_session(db, request.cookies.get(REFRESH_COOKIE))
    _set_auth_cookies(response, access_token, refresh_token)
    return {"status": "ok"}


@router.get("/me", response_model=CurrentUser)
async def me(current_user: CurrentUser = Depends(crud_auth.get_current_user)):
    return current_user


@router.post("/logout")
async def logout(db: SessionDep, request: Request, response: Response):
    await crud_auth.end_session(db, request.cookies.get(REFRESH_COOKIE))
    secure = get_settings().cookie_secure
    response.delete_cookie(key=ACCESS_COOKIE, httponly=True, samesite="lax", secure=secure)
    response.delete_cookie(key=REFRESH_COOKIE, httponly=True, samesite="lax", secure=secure)
    return {"message": "Пользователь успешно вышел из системы"}
