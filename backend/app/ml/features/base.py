"""Базовый тип признака модели и общий контекст для его вычисления.

Признак — объект ``Feature``: код (ключ в ``ModelConfig.weights``), вес по
умолчанию, текст причины на русском и функция ``compute(ctx) -> float в [0,1]``.
Чтобы добавить новый признак: вычислить его в новом файле рядом (см. соседние
модули) и добавить в ``FEATURE_REGISTRY`` (``app/ml/features/__init__.py``) —
больше нигде ничего менять не нужно.

``CustomerContext`` — то, что раньше было локальными переменными внутри одной
большой функции ``extract_features``: расчёт общий для нескольких признаков
(список активных/ожидающих оплаты услуг, доступные средства и т.д.), поэтому
считается один раз на клиента в ``build_context`` и переиспользуется.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable


def _parse_datetime(value: Any) -> datetime | None:
    """Парсит дату из ISO-строки или datetime; возвращает None при ошибке.

    Наивные даты (без таймзоны) трактуются как UTC, чтобы сравнение
    с «сейчас» было корректным.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


@dataclass(frozen=True)
class CustomerContext:
    """Предрасчитанные данные одного клиента, общие для нескольких признаков."""

    customer: dict[str, Any]
    now: datetime
    expires_soon_days: int
    services: list[dict[str, Any]]
    transactions: list[dict[str, Any]]
    balance: float
    bonus_balance: float
    bonus_state: bool
    available_funds: float
    prolong_wait_services: list[dict[str, Any]]
    active_services: list[dict[str, Any]]
    suspended_services: list[dict[str, Any]]
    gone_services: list[dict[str, Any]]
    prolong_wait_cost: float
    expiring_soon: list[dict[str, Any]]
    upcoming_cost: float


@dataclass(frozen=True)
class Feature:
    """Один признак модели."""

    code: str
    default_weight: float
    reason_text: str
    compute: Callable[[CustomerContext], float]

    def value(self, ctx: CustomerContext) -> float:
        return self.compute(ctx)


def build_context(
    customer: dict[str, Any],
    expires_soon_days: int,
    now: datetime | None = None,
) -> CustomerContext:
    """Считает общий контекст клиента один раз — используется всеми признаками.

    Дословный перенос пролога прежней ``extract_features`` (до того, как она
    начинала писать в ``features[...]``), без изменений в математике.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    services = customer.get("services") or []
    transactions = customer.get("transactions") or []

    balance = float(customer.get("balance") or 0)
    bonus_balance = float(customer.get("bonusBalance") or 0)
    bonus_state = bool(customer.get("bonusState"))
    # Доступные средства: основной баланс + бонусы, если их разрешено тратить.
    # Реферальный withdrawBalance сознательно не учитываем: перевод на
    # основной баланс — отдельное действие клиента, на него нельзя
    # полагаться при оценке «хватит ли денег на продление».
    available_funds = balance + (bonus_balance if bonus_state else 0.0)

    prolong_wait_services = [s for s in services if s.get("status") == "prolong_wait"]
    active_services = [s for s in services if s.get("status") == "active"]
    suspended_services = [s for s in services if s.get("status") == "suspended"]
    gone_services = [s for s in services if s.get("status") in ("deleted", "blocked")]

    prolong_wait_cost = sum(float(s.get("price") or 0) for s in prolong_wait_services)

    horizon_seconds = expires_soon_days * 86400
    expiring_soon = []
    for s in active_services:
        expires_at = _parse_datetime(s.get("expiresAt"))
        if expires_at is not None and 0 <= (expires_at - now).total_seconds() <= horizon_seconds:
            expiring_soon.append(s)

    upcoming_cost = prolong_wait_cost + sum(float(s.get("price") or 0) for s in expiring_soon)

    return CustomerContext(
        customer=customer,
        now=now,
        expires_soon_days=expires_soon_days,
        services=services,
        transactions=transactions,
        balance=balance,
        bonus_balance=bonus_balance,
        bonus_state=bonus_state,
        available_funds=available_funds,
        prolong_wait_services=prolong_wait_services,
        active_services=active_services,
        suspended_services=suspended_services,
        gone_services=gone_services,
        prolong_wait_cost=prolong_wait_cost,
        expiring_soon=expiring_soon,
        upcoming_cost=upcoming_cost,
    )
