import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response, status

import app.crud.auth as crud_auth
import app.crud.users as crud_users
from app.core.engine import SessionDep
from app.db.schemas.auth import CurrentUser
from app.db.schemas.users import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])

Actor = Annotated[CurrentUser, Depends(crud_auth.require_admin)]


@router.get("", response_model=list[UserOut])
async def list_users(db: SessionDep, actor: Actor):
    """Суперадмин видит админов и менеджеров, админ только менеджеров"""
    return await crud_users.list_users(db, actor)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(db: SessionDep, data: UserCreate, actor: Actor):
    """Создать менеджера (логин, почта, пароль); поле role=admin создаёт админа, это может только суперадмин"""
    return await crud_users.create_user(db, data, actor)


@router.patch("/{userId}", response_model=UserOut)
async def update_user(db: SessionDep, data: UserUpdate, user_id: Annotated[uuid.UUID, Path(alias="userId")], actor: Actor):
    """Изменить логин, почту или пароль; админов меняет только суперадмин"""
    return await crud_users.update_user(db, user_id, data, actor)


@router.delete("/{userId}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(db: SessionDep, user_id: Annotated[uuid.UUID, Path(alias="userId")], actor: Actor):
    """Удалить пользователя и закрыть его сессии; админов удаляет только суперадмин"""
    await crud_users.delete_user(db, user_id, actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
