import asyncio
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import app.core.authentik_api as authentik_api
from app.core.config import get_settings
from app.core.security import get_password_hash
from app.dao.session import SessionsDAO
from app.dao.user import UsersDAO
from app.db.models.users import User
from app.db.schemas.auth import CurrentUser
from app.db.schemas.users import UserCreate, UserUpdate

logger = logging.getLogger(__name__)


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


@asynccontextmanager
async def _authentik_errors():
    """Сбой Authentik -> 502: изменение в панели не сохраняется, чтобы логин/пароль не разошлись"""
    try:
        yield
    except authentik_api.AuthentikSyncError as exc:
        logger.warning("Синхронизация с Authentik не удалась: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            # Чаще всего Authentik ещё стартует (после docker compose up это ~2 минуты)
            detail="Authentik недоступен или ещё запускается — изменения не сохранены. Повторите через минуту",
        ) from exc


def _forbidden() -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")


def _check_can_manage(actor: CurrentUser, target: User) -> None:
    """Админов создаёт и меняет только суперадмин; админ управляет менеджерами"""
    if target.role == "admin" and actor.role != "superadmin":
        raise _forbidden()


async def list_users(db: AsyncSession, actor: CurrentUser) -> list[User]:
    """Суперадмин видит админов и менеджеров, админ только менеджеров"""
    return await UsersDAO.list_all(db, role=None if actor.role == "superadmin" else "manager")


async def create_user(db: AsyncSession, data: UserCreate, actor: CurrentUser) -> User:
    if data.role == "admin" and actor.role != "superadmin":
        raise _forbidden()
    await _check_unique(db, data.login, data.email)
    password_hash = await asyncio.to_thread(get_password_hash, data.password)
    # Сначала Authentik: если он недоступен, пользователь не появится и в панели
    async with _authentik_errors():
        created_pk = await authentik_api.upsert_user(login=data.login, email=data.email, password=data.password)
    try:
        return await UsersDAO.add(db, login=data.login, email=data.email, password_hash=password_hash, role=data.role)
    except IntegrityError:
        await db.rollback()
        if created_pk is not None:
            await authentik_api.delete_user_by_pk(created_pk)
        raise _conflict("Логин или почта уже заняты")


async def _get_or_404(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await UsersDAO.find_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    return user


async def update_user(db: AsyncSession, user_id: uuid.UUID, data: UserUpdate, actor: CurrentUser) -> User:
    user = await _get_or_404(db, user_id)
    _check_can_manage(actor, user)
    values = data.model_dump(exclude_none=True)
    if not values:
        return user
    await _check_unique(db, values.get("login"), values.get("email"), user.id)
    password = values.pop("password", None)
    if password is not None:
        values["password_hash"] = await asyncio.to_thread(get_password_hash, password)
    try:
        # Логин перечитывается под блокировкой строки после хэширования: параллельное переименование
        # либо уже закоммичено (увидим новый логин), либо ждёт нас — сессии закроются у актуального логина
        old_login = await UsersDAO.lock_login(db, user.id)
        if old_login is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
        await UsersDAO.update_by_id_no_commit(db, user.id, **values)
        if "login" in values or "password_hash" in values:
            # Смена логина или пароля закрывает старые сессии менеджера в той же транзакции
            await SessionsDAO.delete_by_login_no_commit(db, old_login)
        # Authentik — под блокировкой строки и до commit: при его сбое изменение в панели откатится
        async with _authentik_errors():
            await authentik_api.upsert_user(
                login=values.get("login", old_login), email=values.get("email", user.email), password=password, old_login=old_login
            )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise _conflict("Логин или почта уже заняты")
    except HTTPException:
        await db.rollback()
        raise
    await db.refresh(user)
    return user


async def delete_user(db: AsyncSession, user_id: uuid.UUID, actor: CurrentUser) -> None:
    user = await _get_or_404(db, user_id)
    _check_can_manage(actor, user)
    # Удаление пользователя и закрытие его сессий — одним commit
    try:
        await SessionsDAO.delete_by_login_no_commit(db, user.login)
        await UsersDAO.delete_by_id_no_commit(db, user.id)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise _conflict("Не удалось удалить пользователя")
    await authentik_api.delete_user(user.login)
