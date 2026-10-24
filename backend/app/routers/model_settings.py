from typing import Any

from fastapi import APIRouter, Body, Depends

import app.crud.auth as crud_auth
import app.crud.model_settings as crud_model_settings
from app.core.engine import SessionDep
from app.core.openapi import error_responses
from app.db.schemas.model_settings import ModelSettingsOut, ModelSettingsPatchOut

router = APIRouter(
    prefix="/model",
    tags=["model"],
    dependencies=[Depends(crud_auth.get_current_user)],
    responses=error_responses(401),
)

# Тело PATCH — произвольный JSON-объект с частичными настройками (не схема Pydantic).
_PATCH_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": {
                    "type": "object",
                    "description": "Частичные настройки модели; передаются только изменяемые ключи",
                },
                "examples": {
                    "asOf": {
                        "summary": "Момент оценки (на какую дату считать риск)",
                        "value": {"asOf": "2026-10-19T15:00:00Z"},
                    },
                    "thresholds": {
                        "summary": "Пороги уровней по score 0..100",
                        "value": {"thresholds": {"high": 70, "medium": 35}},
                    },
                    "weight": {
                        "summary": "Изменить вес признака модели",
                        "value": {"weights": {"has_prolong_wait": 3.5}},
                    },
                    "mixed": {
                        "summary": "Несколько параметров сразу",
                        "value": {"bias": -2.5, "horizonDays": 30},
                    },
                },
            }
        },
    }
}


@router.get("/settings", response_model=ModelSettingsOut)
async def get_settings(db: SessionDep) -> ModelSettingsOut:
    """Текущие эффективные настройки модели и дефолты"""
    return await crud_model_settings.get_view(db)


@router.patch(
    "/settings",
    response_model=ModelSettingsPatchOut,
    dependencies=[Depends(crud_auth.require_admin)],
    responses=error_responses(403, 503),
    openapi_extra=_PATCH_BODY,
)
async def patch_settings(db: SessionDep, body: Any = Body(...)) -> ModelSettingsPatchOut:
    """Частичное обновление настроек модели с пересчётом (только администратор).

    Тело — произвольный JSON-объект с изменяемыми ключами: ``asOf`` (дата оценки),
    ``weights`` (веса признаков), ``bias``, ``threshold``, ``thresholds`` (пороги
    уровней), ``expiresSoonDays``, ``horizonDays``. Неизвестные ключи сохраняются.
    """
    return await crud_model_settings.patch_settings(db, body)


@router.delete(
    "/settings/{section}/{key}",
    response_model=ModelSettingsPatchOut,
    dependencies=[Depends(crud_auth.require_admin)],
    responses=error_responses(403, 404, 503),
)
async def delete_setting(db: SessionDep, section: str, key: str) -> ModelSettingsPatchOut:
    """Удалить пункт настроек (например, признак модели: weights/имя) и пересчитать (только администратор)"""
    return await crud_model_settings.delete_setting(db, section, key)
