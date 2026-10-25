import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.analysis as analysis
import app.crud.recalc as recalc
from app.dao.audit_log import AuditLogDAO
from app.dao.model_settings import ModelSettingsDAO
from app.db.models.audit import AuditLog
from app.db.models.model_settings import ModelSettings
from app.db.schemas.audit import AuditLogEntryOut, AuditLogPage
from app.db.schemas.auth import CurrentUser
from app.db.schemas.model_settings import ModelSettingsOut, ModelSettingsPatchOut


def _safe_uuid(value: str | None) -> uuid.UUID | None:
    """uid из CurrentUser -> UUID или None (суперадмин: uid='superadmin', не UUID)"""
    try:
        return uuid.UUID(value) if value else None
    except ValueError:
        return None


def _invalid_body(msg: str) -> HTTPException:
    """422 в формате FastAPI с текстом ошибки модели"""
    return HTTPException(status_code=422, detail=[{"loc": ["body"], "msg": msg, "type": "value_error"}])


async def get_audit(session: AsyncSession, page: int, page_size: int) -> AuditLogPage:
    """Страница истории изменений настроек (GET /model/settings/audit)"""
    rows = await AuditLogDAO.list_page(session, page=page, page_size=page_size)
    total = await AuditLogDAO.count(session)
    return AuditLogPage(
        items=[
            AuditLogEntryOut(
                id=row.id, actor_login=row.actor_login, actor_role=row.actor_role,
                action=row.action, section=row.section, before=row.before, after=row.after,
                created_at=row.created_at,
            )
            for row in rows
        ],
        total=total, page=page, page_size=page_size,
    )


async def get_view(session: AsyncSession) -> ModelSettingsOut:
    """Эффективные настройки, дефолты и время обновления (GET /model/settings)"""
    row = await ModelSettingsDAO.find_by_id(session, 1)
    return ModelSettingsOut(
        settings=await recalc.effective_settings(session),
        defaults=analysis.default_settings(),
        updated_at=row.updated_at,
    )


async def patch_settings(session: AsyncSession, body: Any, actor: CurrentUser) -> ModelSettingsPatchOut:
    """Частичное обновление настроек с пересчётом; всё под advisory-lock в одной транзакции"""
    if not isinstance(body, dict):
        raise _invalid_body("Тело запроса должно быть JSON-объектом")

    # Слияние и валидация — после взятия блокировки (два PATCH не теряют друг друга)
    await recalc.acquire_lock(session)
    _, removed = recalc.split_stored(await ModelSettingsDAO.get(session))
    before = await recalc.effective_settings(session)
    merged = recalc.deep_merge(before, body)
    try:
        normalized = analysis.validate_settings(merged)
    except ValueError as exc:
        raise _invalid_body(str(exc))

    # Пункт, который снова задан в теле запроса, перестаёт считаться удалённым
    still_removed = [p for p in removed if not _has_path(body, p)]
    return await _save_and_recalculate(session, normalized, still_removed, actor=actor, action="patch", before=before)


def _has_path(settings: dict, path: str) -> bool:
    section, _, key = path.partition(".")
    return isinstance(settings.get(section), dict) and key in settings[section]


async def _save_and_recalculate(
    session: AsyncSession,
    settings: dict,
    removed: list[str],
    *,
    actor: CurrentUser,
    action: str,
    before: dict,
    section: str | None = None,
) -> ModelSettingsPatchOut:
    stored = {**settings, recalc.REMOVED_KEY: removed} if removed else settings
    await ModelSettingsDAO.save(session, stored)
    summary = await recalc.recalculate(session, "settings")

    # В той же транзакции/advisory-lock, что и сохранение настроек — не через
    # AuditLogDAO.add() (та коммитит сама и разорвала бы атомарность).
    session.add(AuditLog(
        actor_login=actor.login, actor_role=actor.role, user_id=_safe_uuid(actor.uid),
        action=action, section=section, before=before, after=settings,
    ))

    # Ответ собирается до commit, пока держим advisory-lock: иначе параллельный PATCH успеет
    # подменить настройки и ответ смешает чужие настройки с нашей version
    updated_at = (await session.execute(select(ModelSettings.updated_at).where(ModelSettings.id == 1))).scalar_one()
    out = ModelSettingsPatchOut(
        settings=await recalc.effective_settings(session),
        defaults=analysis.default_settings(),
        updated_at=updated_at,
        version=summary.version,
        recalculated_at=summary.recalculated_at,
    )
    await session.commit()
    return out


async def delete_setting(session: AsyncSession, section: str, key: str, actor: CurrentUser) -> ModelSettingsPatchOut:
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
    return await _save_and_recalculate(
        session, normalized, removed if path in removed else [*removed, path],
        actor=actor, action="delete", before=current, section=path,
    )
