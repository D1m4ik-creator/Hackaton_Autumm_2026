import uuid

from pydantic import Field

from app.db.schemas.common import CamelModel, UtcDateTime


class ShareLinkCreateIn(CamelModel):
    """Тело POST /share-links"""

    label: str | None = Field(default=None, max_length=200)
    expires_in_days: int = Field(default=7, ge=1, le=90)


class ShareLinkOut(CamelModel):
    """Метаданные ссылки без самого токена (GET /share-links)"""

    id: uuid.UUID
    label: str | None
    created_by_login: str
    created_at: UtcDateTime
    expires_at: UtcDateTime
    revoked_at: UtcDateTime | None
    active: bool


class ShareLinkCreatedOut(ShareLinkOut):
    """Ответ на создание — единственный раз содержит сырой токен"""

    token: str
