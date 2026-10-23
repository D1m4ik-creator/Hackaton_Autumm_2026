import uuid
from hmac import compare_digest

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

import app.crud.users as crud_user
from app.core.config import get_settings
from app.core.engine import SessionDep
from app.core.security import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    create_access_token,
    create_refresh_token,
    get_user_id,
    hash_token,
    refresh_decode_token,
)
from app.dao.user import UsersDAO
from app.db.schemas.users import UserCreate, UserLogin, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


async def _issue_tokens(db: AsyncSession, response: Response, user_id: uuid.UUID) -> None:
    """Выдаёт пару токенов: хэш refresh сохраняется в БД, сами токены уходят в cookie"""
    jwt_settings = get_settings().jwt
    access_token = create_access_token({"sub": str(user_id)})
    refresh_token = create_refresh_token({"sub": str(user_id)})
    await UsersDAO.set_refresh_token_hash(db, user_id, hash_token(refresh_token))

    response.set_cookie(
        key=ACCESS_COOKIE,
        value=access_token,
        httponly=True,
        samesite="lax",
        max_age=jwt_settings.access_token_expire_minutes * 60,
    )
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh_token,
        httponly=True,
        samesite="lax",
        max_age=jwt_settings.refresh_token_expire_days * 60 * 60 * 24,
    )


@router.post("/create_user/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(db: SessionDep, user_in: UserCreate):
    if await crud_user.get_by_email(db, email=user_in.email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Пользователь с такой почтой уже существует")
    if await crud_user.get_by_name(db, name=user_in.name):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Это имя уже занято")

    return await crud_user.create(db, obj_in=user_in)


@router.post("/login_user/")
async def auth_user(db: SessionDep, user_data: UserLogin, response: Response):
    user = await crud_user.authenticate_user(db, email=user_data.email, password=user_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверная почта или пароль")

    await _issue_tokens(db, response, user.id)
    return {"message": "Успешная авторизация"}


@router.post("/logout/")
async def logout_user(db: SessionDep, request: Request, response: Response):
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if refresh_token:
        try:
            user_id = get_user_id(refresh_decode_token(refresh_token))
            await UsersDAO.set_refresh_token_hash(db, user_id, None)
        except HTTPException:
            # Токен битый или просроченный: в базе сбрасывать нечего, cookie всё равно чистим
            pass

    response.delete_cookie(key=ACCESS_COOKIE)
    response.delete_cookie(key=REFRESH_COOKIE)
    return {"message": "Пользователь успешно вышел из системы"}


@router.post("/refresh/")
async def refresh(db: SessionDep, request: Request, response: Response):
    old_refresh = request.cookies.get(REFRESH_COOKIE)
    user_id = get_user_id(refresh_decode_token(old_refresh))

    user = await UsersDAO.find_by_id(db, user_id)
    stored_hash = user.refresh_token_hash if user else None
    if not stored_hash or not compare_digest(stored_hash, hash_token(old_refresh)):
        if user:
            # Пришёл не актуальный refresh (возможно украденный): сбрасываем сессию целиком
            await UsersDAO.set_refresh_token_hash(db, user.id, None)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token не действителен")

    await _issue_tokens(db, response, user.id)
    return {"status": "ok"}
