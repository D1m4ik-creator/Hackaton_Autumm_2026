import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response, status

import app.crud.auth as crud_auth
import app.crud.users as crud_users
from app.core.engine import SessionDep
from app.db.schemas.users import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(crud_auth.require_admin)])


@router.get("", response_model=list[UserOut])
async def list_users(db: SessionDep):
    """Список менеджеров (только администратор)"""
    return await crud_users.list_users(db)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(db: SessionDep, data: UserCreate):
    """Создать менеджера: логин, почта, пароль (только администратор)"""
    return await crud_users.create_user(db, data)


@router.patch("/{userId}", response_model=UserOut)
async def update_user(db: SessionDep, data: UserUpdate, user_id: Annotated[uuid.UUID, Path(alias="userId")]):
    """Изменить логин, почту или пароль менеджера (только администратор)"""
    return await crud_users.update_user(db, user_id, data)


@router.delete("/{userId}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(db: SessionDep, user_id: Annotated[uuid.UUID, Path(alias="userId")]):
    """Удалить менеджера и закрыть его сессии (только администратор)"""
    await crud_users.delete_user(db, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
