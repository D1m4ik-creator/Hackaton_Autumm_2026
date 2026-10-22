from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import SessionDep
from app.core.security import access_decode_token, get_password_hash, get_token, get_user_id, verify_password
from app.dao.user import UsersDAO
from app.db.models.users import User
from app.db.schemas.users import UserCreate


async def get_current_user(db: SessionDep, token: str = Depends(get_token)) -> User:
    payload = access_decode_token(token)
    user = await UsersDAO.find_by_id(db, get_user_id(payload))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь не найден")
    return user


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    return await UsersDAO.find_one_or_none(db, email=email)


async def get_by_name(db: AsyncSession, name: str) -> User | None:
    return await UsersDAO.find_one_or_none(db, name=name)


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    user = await get_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def create(db: AsyncSession, obj_in: UserCreate) -> User:
    return await UsersDAO.add(
        db,
        name=obj_in.name,
        email=obj_in.email,
        hashed_password=get_password_hash(obj_in.password),
    )
