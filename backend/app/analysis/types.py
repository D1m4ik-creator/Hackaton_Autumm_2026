"""Контракт модуля анализа: входные и выходные типы.

Чистый Python без БД, HTTP и SQLAlchemy. Владелец — ML-команда;
инфраструктура зависит только от этих типов и функций из ``app.analysis``.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

Level = Literal["high", "medium", "low", "no_data"]


@dataclass(frozen=True)
class AccountData:
    """Аккаунт клиента на вход модели"""

    id: int
    email: str
    balance: int
    withdraw_balance: int
    total_replenished: int
    bonus_balance: int
    bonus_state: str


@dataclass(frozen=True)
class ServiceData:
    """Услуга на вход модели"""

    id: int
    name: str
    owner_id: int
    payment_term: str
    auto_prolong: bool
    created_at: datetime
    expires_at: datetime
    status: str
    price: int


@dataclass(frozen=True)
class TransactionData:
    """Транзакция на вход модели"""

    id: int
    amount: int
    status: str
    performed_at: datetime | None
    created_at: datetime
    type: str
    service_id: int


@dataclass(frozen=True)
class SourceData:
    """Полный снимок исходных данных на вход модели"""

    accounts: list[AccountData]
    services: list[ServiceData]
    transactions: list[TransactionData]


@dataclass(frozen=True)
class Reason:
    """Причина риска"""

    code: str  # машинный код причины
    text: str  # понятная фраза по-русски


@dataclass(frozen=True)
class CustomerRisk:
    """Оценка риска по одному клиенту"""

    account_id: int
    score: int | None  # 0..100; None только при level = "no_data"
    level: Level
    reasons: list[Reason]  # первая — главная (идёт в reasonShort)
    expected_loss_cents: int  # >= 0, целые евроценты
    details: dict = field(default_factory=dict)  # JSON-сериализуемое, в карточку как есть


@dataclass(frozen=True)
class AnalysisResult:
    """Результат анализа по всем клиентам"""

    customers: list[CustomerRisk]
    loss_explanation: str  # смысл денежной суммы для панели
