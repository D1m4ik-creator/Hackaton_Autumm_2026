import uuid
from datetime import datetime

from sqlalchemy import DateTime, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ShareLink(Base):
    """Публичная read-only ссылка на отчёт: хранится только хэш токена.

    Сырой токен отдаётся пользователю один раз, при создании, и больше
    никогда не читается из БД (та же схема, что и у refresh-токенов сессий).
    """

    __tablename__ = "share_links"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    label: Mapped[str | None] = mapped_column(Text)
    created_by_login: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
