from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Transaction(Base):
    """Транзакция по услуге из снимка исходных данных"""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    performed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    service_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("services.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    __table_args__ = (
        CheckConstraint("amount >= 0 AND amount <= 1000", name="amount_range"),
        CheckConstraint("status IN ('performed', 'not_performed')", name="status_valid"),
        CheckConstraint("type IN ('prolong', 'order')", name="type_valid"),
    )
