from sqlalchemy import BigInteger, CheckConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Account(Base):
    """Аккаунт клиента из снимка исходных данных"""

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    balance: Mapped[int] = mapped_column(BigInteger, nullable=False)
    withdraw_balance: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_replenished: Mapped[int] = mapped_column(BigInteger, nullable=False)
    bonus_balance: Mapped[int] = mapped_column(BigInteger, nullable=False)
    bonus_state: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint("balance >= 0", name="balance_non_negative"),
        CheckConstraint("withdraw_balance >= 0", name="withdraw_balance_non_negative"),
        CheckConstraint("total_replenished >= 0", name="total_replenished_non_negative"),
        CheckConstraint("bonus_balance >= 0", name="bonus_balance_non_negative"),
        CheckConstraint("bonus_state IN ('locked', 'unlocked')", name="bonus_state_valid"),
    )
