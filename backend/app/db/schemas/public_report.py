from app.db.schemas.common import CamelModel, UtcDateTime
from app.db.schemas.customers import CustomerService, CustomerTransactions, Level, ReasonOut


class PublicCustomerItem(CamelModel):
    """Строка таблицы клиентов в публичном read-only отчёте — без email (PII)"""

    id: int
    balance: int
    total_replenished: int
    risk_score: int | None
    level: Level
    expected_loss_cents: int
    reason_short: str


class PublicCustomerPage(CamelModel):
    """Страница публичного списка клиентов"""

    items: list[PublicCustomerItem]
    total: int
    page: int
    page_size: int


class PublicCustomerCard(CamelModel):
    """Карточка клиента в публичном read-only отчёте — без email"""

    id: int
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
