import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class User(Base):
    """Менеджер, которого создал администратор; главный администратор живёт в .env и в таблице не хранится"""

    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('admin', 'manager')", name="role"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    login: Mapped[str] = mapped_column(unique=True)
    email: Mapped[str] = mapped_column(unique=True)
    password_hash: Mapped[str]
    role: Mapped[str] = mapped_column(default="manager", server_default="manager")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
