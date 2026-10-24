from typing import Any

from fastapi import APIRouter, Body, Depends

import app.crud.auth as crud_auth
import app.crud.model_settings as crud_model_settings
from app.core.engine import SessionDep
from app.db.schemas.model_settings import ModelSettingsOut, ModelSettingsPatchOut

router = APIRouter(
    prefix="/model",
    tags=["model"],
    dependencies=[Depends(crud_auth.get_current_user)],
)


@router.get("/settings", response_model=ModelSettingsOut)
async def get_settings(db: SessionDep) -> ModelSettingsOut:
    """Текущие эффективные настройки модели и дефолты"""
    return await crud_model_settings.get_view(db)


@router.patch("/settings", response_model=ModelSettingsPatchOut, dependencies=[Depends(crud_auth.require_admin)])
async def patch_settings(db: SessionDep, body: Any = Body(...)) -> ModelSettingsPatchOut:
    """Частичное обновление настроек модели с пересчётом (только администратор)"""
    return await crud_model_settings.patch_settings(db, body)


@router.delete(
    "/settings/{section}/{key}",
    response_model=ModelSettingsPatchOut,
    dependencies=[Depends(crud_auth.require_admin)],
    responses={404: {"description": "Секция или пункт настроек не найдены"}},
)
async def delete_setting(db: SessionDep, section: str, key: str) -> ModelSettingsPatchOut:
    """Удалить пункт настроек (например, признак модели: weights/имя) и пересчитать (только администратор)"""
    return await crud_model_settings.delete_setting(db, section, key)
