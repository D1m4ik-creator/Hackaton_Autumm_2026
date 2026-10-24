from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Service(Base):
    """Услуга клиента из снимка исходных данных"""

    __tablename__ = "services"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    payment_term: Mapped[str] = mapped_column(Text, nullable=False)
    auto_prolong: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[int] = mapped_column(BigInteger, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "payment_term IN ('hour', 'week', 'month', 'quarter_year', 'half_year', 'year')",
            name="payment_term_valid",
        ),
        CheckConstraint(
            "status IN ('active', 'blocked', 'deleted', 'suspended', 'prolong_wait')",
            name="status_valid",
        ),
        CheckConstraint("price >= 0", name="price_non_negative"),
    )
