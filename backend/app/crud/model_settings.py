from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

import app.analysis as analysis
import app.crud.recalc as recalc
from app.dao.model_settings import ModelSettingsDAO
from app.db.schemas.model_settings import ModelSettingsOut, ModelSettingsPatchOut


def _invalid_body(msg: str) -> HTTPException:
    """422 в формате FastAPI с текстом ошибки модели"""
    return HTTPException(status_code=422, detail=[{"loc": ["body"], "msg": msg, "type": "value_error"}])


async def get_view(session: AsyncSession) -> ModelSettingsOut:
    """Эффективные настройки, дефолты и время обновления (GET /model/settings)"""
    row = await ModelSettingsDAO.find_by_id(session, 1)
    return ModelSettingsOut(
        settings=await recalc.effective_settings(session),
        defaults=analysis.default_settings(),
        updated_at=row.updated_at,
    )


async def patch_settings(session: AsyncSession, body: Any) -> ModelSettingsPatchOut:
    """Частичное обновление настроек с пересчётом; всё под advisory-lock в одной транзакции"""
    if not isinstance(body, dict):
        raise _invalid_body("Тело запроса должно быть JSON-объектом")

    # Слияние и валидация — после взятия блокировки (два PATCH не теряют друг друга)
    await recalc.acquire_lock(session)
    _, removed = recalc.split_stored(await ModelSettingsDAO.get(session))
    merged = recalc.deep_merge(await recalc.effective_settings(session), body)
    try:
        normalized = analysis.validate_settings(merged)
    except ValueError as exc:
        raise _invalid_body(str(exc))

    # Пункт, который снова задан в теле запроса, перестаёт считаться удалённым
    still_removed = [p for p in removed if not _has_path(body, p)]
    return await _save_and_recalculate(session, normalized, still_removed)


def _has_path(settings: dict, path: str) -> bool:
    section, _, key = path.partition(".")
    return isinstance(settings.get(section), dict) and key in settings[section]


async def _save_and_recalculate(session: AsyncSession, settings: dict, removed: list[str]) -> ModelSettingsPatchOut:
    stored = {**settings, recalc.REMOVED_KEY: removed} if removed else settings
    await ModelSettingsDAO.save(session, stored)
    summary = await recalc.recalculate(session, "settings")
    await session.commit()

    row = await ModelSettingsDAO.find_by_id(session, 1)
    return ModelSettingsPatchOut(
        settings=await recalc.effective_settings(session),
        defaults=analysis.default_settings(),
        updated_at=row.updated_at,
        version=summary.version,
        recalculated_at=summary.recalculated_at,
    )


async def delete_setting(session: AsyncSession, section: str, key: str) -> ModelSettingsPatchOut:
    """Удаляет пункт настроек settings[section][key] (например, признак модели) и пересчитывает"""
    await recalc.acquire_lock(session)
    _, removed = recalc.split_stored(await ModelSettingsDAO.get(session))
    current = await recalc.effective_settings(session)

    if section not in current:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Секция настроек не найдена")
    if not isinstance(current[section], dict):
        raise _invalid_body(f"«{section}» не является набором пунктов, удалять из него нечего")
    if key not in current[section]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пункт настроек не найден")

    remaining = {**current, section: {k: v for k, v in current[section].items() if k != key}}
    try:
        normalized = analysis.validate_settings(remaining)
    except ValueError as exc:
        raise _invalid_body(str(exc))

    path = f"{section}.{key}"
    return await _save_and_recalculate(session, normalized, removed if path in removed else [*removed, path])
