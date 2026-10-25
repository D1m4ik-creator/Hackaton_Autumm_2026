from typing import Literal

from app.db.schemas.common import CamelModel, UtcDateTime


class AuditLogEntryOut(CamelModel):
    """Одна запись истории изменений настроек модели"""

    id: int
    actor_login: str
    actor_role: str
    action: Literal["patch", "delete"]
    section: str | None
    before: dict
    after: dict
    created_at: UtcDateTime


class AuditLogPage(CamelModel):
    """Страница истории изменений (GET /model/settings/audit)"""

    items: list[AuditLogEntryOut]
    total: int
    page: int
    page_size: int
