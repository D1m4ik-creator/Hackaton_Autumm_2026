from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Integer, SmallInteger, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class RiskSummary(Base):
    """Сводка по всем клиентам (одна строка id=1): её читают сводка, /metrics и SSE"""

    __tablename__ = "risk_summary"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    reason: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'init'"))
    customers_total: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    by_level: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    expected_loss_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    loss_explanation: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recalculated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (CheckConstraint("id = 1", name="singleton"),)
