from typing import Literal

from app.db.schemas.common import CamelModel, UtcDateTime

# Уровни риска клиента (в JSON как есть)
Level = Literal["high", "medium", "low", "no_data"]


class ReasonOut(CamelModel):
    """Одна причина оценки риска"""

    code: str
    text: str


class CustomerListItem(CamelModel):
    """Строка таблицы клиентов (GET /customers)"""

    id: int
    email: str
    balance: int
    total_replenished: int
    risk_score: int | None
    level: Level
    expected_loss_cents: int
    reason_short: str


class CustomerPage(CamelModel):
    """Страница списка клиентов"""

    items: list[CustomerListItem]
    total: int
    page: int
    page_size: int


class CustomerService(CamelModel):
    """Услуга клиента в карточке"""

    id: int
    name: str
    status: str
    price: int
    auto_prolong: bool
    payment_term: str
    created_at: UtcDateTime
    expires_at: UtcDateTime


class CustomerTransactions(CamelModel):
    """Сводка по транзакциям клиента"""

    total: int
    performed: int
    not_performed: int


class CustomerCard(CamelModel):
    """Карточка клиента (GET /customers/{customerId})"""

    id: int
    email: str
    balance: int
    withdraw_balance: int
    total_replenished: int
    bonus_balance: int
    bonus_state: str
    risk_score: int | None
    level: Level
    expected_loss_cents: int
    reason_short: str
    reasons: list[ReasonOut]
    details: dict
    services: list[CustomerService]
    transactions: CustomerTransactions
    as_of: UtcDateTime | None
    calculated_at: UtcDateTime | None
