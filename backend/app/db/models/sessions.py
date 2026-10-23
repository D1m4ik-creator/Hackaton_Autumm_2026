import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AuthSession(Base):
    """Сессия входа: одна на браузер, хранит хэш актуального refresh токена"""

    __tablename__ = "auth_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    login: Mapped[str] = mapped_column(index=True)
    refresh_token_hash: Mapped[str]
    # Предыдущий хэш и время замены: повтор старого токена сразу после замены — это параллельный запрос, а не кража
    previous_token_hash: Mapped[str | None]
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
