from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, SmallInteger, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class RiskResult(Base):
    """Результат оценки риска по одному клиенту (строка на клиента)"""

    __tablename__ = "risk_results"

    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True, autoincrement=False
    )
    score: Mapped[int | None] = mapped_column(SmallInteger)
    level: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    reason_short: Mapped[str] = mapped_column(Text, nullable=False)
    reasons: Mapped[list] = mapped_column(JSONB, nullable=False)
    expected_loss_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="score_range"),
        CheckConstraint("level IN ('high', 'medium', 'low', 'no_data')", name="level_valid"),
        CheckConstraint("expected_loss_cents >= 0", name="expected_loss_non_negative"),
        CheckConstraint("(level = 'no_data') = (score IS NULL)", name="no_data_iff_null_score"),
    )
