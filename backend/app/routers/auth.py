from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

import app.crud.auth as crud_auth
from app.core.limiter import limiter, login_limit, refresh_limit
from app.core.login_guard import login_guard
from app.core.config import get_settings
from app.core.engine import SessionDep
from app.core.openapi import error_responses
from app.core.security import ACCESS_COOKIE, REFRESH_COOKIE
from app.db.schemas.auth import CurrentUser, UserLogin

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", responses=error_responses(401, 429))
@limiter.limit(login_limit)
async def login(request: Request, db: SessionDep, user_data: UserLogin, response: Response):
    retry_after = await login_guard.retry_after(user_data.login)
    if retry_after is not None:
        # Логин временно заблокирован из-за серии неудачных попыток (и верный пароль пока отвергается)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Слишком много неудачных попыток, попробуйте позже",
            headers={"Retry-After": str(retry_after)},
        )

    user = await crud_auth.authenticate(db, user_data.login, user_data.password)
    if not user:
        await login_guard.record_failure(user_data.login)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")

    await login_guard.record_success(user_data.login)
    access_token, refresh_token = await crud_auth.start_session(db, user.login, user.uid)
    crud_auth.set_auth_cookies(response, access_token, refresh_token)
    return {"message": "Успешная авторизация"}


@router.post("/refresh", responses=error_responses(401, 429))
@limiter.limit(refresh_limit)
async def refresh(request: Request, db: SessionDep, response: Response):
    access_token, refresh_token = await crud_auth.rotate_session(db, request.cookies.get(REFRESH_COOKIE))
    crud_auth.set_auth_cookies(response, access_token, refresh_token)
    return {"status": "ok"}


@router.get("/me", response_model=CurrentUser, responses=error_responses(401))
async def me(current_user: CurrentUser = Depends(crud_auth.get_current_user)):
    return current_user


@router.post("/logout")
async def logout(db: SessionDep, request: Request, response: Response):
    await crud_auth.end_session(db, request.cookies.get(REFRESH_COOKIE))
    secure = get_settings().cookie_secure
    response.delete_cookie(key=ACCESS_COOKIE, httponly=True, samesite="lax", secure=secure)
    response.delete_cookie(key=REFRESH_COOKIE, httponly=True, samesite="lax", secure=secure)
    return {"message": "Пользователь успешно вышел из системы"}
