from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, SmallInteger, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ModelSettings(Base):
    """Сохранённые настройки модели анализа: одна строка id=1, только сохранённое без дефолтов"""

    __tablename__ = "model_settings"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (CheckConstraint("id = 1", name="singleton"),)
