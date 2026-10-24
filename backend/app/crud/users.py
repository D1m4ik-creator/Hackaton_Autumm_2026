import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import get_password_hash
from app.dao.session import SessionsDAO
from app.dao.user import UsersDAO
from app.db.models.users import User
from app.db.schemas.users import UserCreate, UserUpdate


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


async def _check_unique(db: AsyncSession, login: str | None, email: str | None, user_id: uuid.UUID | None = None):
    if login and login == get_settings().admin.login:
        raise _conflict("Этот логин занят главным администратором")
    if login:
        found = await UsersDAO.find_one_or_none(db, login=login)
        if found and found.id != user_id:
            raise _conflict("Логин уже занят")
    if email:
        found = await UsersDAO.find_one_or_none(db, email=email)
        if found and found.id != user_id:
            raise _conflict("Почта уже занята")


async def list_users(db: AsyncSession) -> list[User]:
    return await UsersDAO.list_all(db)


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    await _check_unique(db, data.login, data.email)
    try:
        return await UsersDAO.add(
            db, login=data.login, email=data.email, password_hash=get_password_hash(data.password), role="manager"
        )
    except IntegrityError:
        await db.rollback()
        raise _conflict("Логин или почта уже заняты")


async def _get_or_404(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await UsersDAO.find_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    return user


async def update_user(db: AsyncSession, user_id: uuid.UUID, data: UserUpdate) -> User:
    user = await _get_or_404(db, user_id)
    values = data.model_dump(exclude_none=True)
    if not values:
        return user
    await _check_unique(db, values.get("login"), values.get("email"), user.id)
    old_login = user.login
    if "password" in values:
        values["password_hash"] = get_password_hash(values.pop("password"))
    try:
        await UsersDAO.update_by_id(db, user.id, **values)
    except IntegrityError:
        await db.rollback()
        raise _conflict("Логин или почта уже заняты")
    if "login" in values or "password_hash" in values:
        # Смена логина или пароля закрывает старые сессии менеджера
        await SessionsDAO.delete_by_login(db, old_login)
    await db.refresh(user)
    return user


async def delete_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    user = await _get_or_404(db, user_id)
    await SessionsDAO.delete_by_login(db, user.login)
    await UsersDAO.delete_by_id(db, user.id)
