import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AuditLog(Base):
    """Запись истории изменений настроек модели: кто/когда/что было -> что стало.

    actor_login/actor_role — снимок на момент действия, не только FK: суперадмин
    живёт в .env и не имеет строки в users, а обычного пользователя можно
    удалить насовсем (без soft-delete) — без снимка история идентичности
    терялась бы.
    """

    __tablename__ = "model_settings_audit"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    actor_login: Mapped[str] = mapped_column(Text)
    actor_role: Mapped[str] = mapped_column(Text)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(Text)
    section: Mapped[str | None] = mapped_column(Text)
    before: Mapped[dict] = mapped_column(JSONB, nullable=False)
    after: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
