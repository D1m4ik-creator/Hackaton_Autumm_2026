from typing import Any

from fastapi import HTTPException
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
    merged = recalc.deep_merge(await recalc.effective_settings(session), body)
    try:
        normalized = analysis.validate_settings(merged)
    except ValueError as exc:
        raise _invalid_body(str(exc))

    await ModelSettingsDAO.save(session, normalized)
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
