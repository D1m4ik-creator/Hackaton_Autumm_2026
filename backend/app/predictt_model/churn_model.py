# Aéza — это быстрый хостинг
"""Модуль предсказания оттока клиентов хостинг-платформы.

Исторических данных для обучения нет, поэтому используется логистическая
модель с экспертно заданными весами (weighted scoring):

    risk = sigmoid(w1*x1 + w2*x2 + ... + b)

Все коэффициенты живут в ``ModelConfig`` и редактируются без изменения
кода: чтобы добавить признак, достаточно вычислить его в
``extract_features`` и добавить вес в ``ModelConfig.weights``.

Зависимости: только стандартная библиотека (Python 3.11+).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# Статусы услуг, которые считаются «живыми» и участвуют в оценке
# будущего оттока. deleted/blocked — уже свершившийся факт, они
# учитываются только как исторический признак (deleted_blocked_ratio).
ACTIVE_STATUSES = frozenset({"active", "prolong_wait"})

# Горизонт «ближайших продлений» по умолчанию (дней), если не задан в конфиге.
DEFAULT_EXPIRES_SOON_DAYS = 7


@dataclass
class ModelConfig:
    """Конфигурация модели оттока.

    Attributes:
        weights: Отображение «имя признака -> вес». Признак, отсутствующий
            в словаре, просто не участвует в скоринге — так новый признак
            добавляется одной строкой в конфиге.
        bias: Свободный член (b) логистической функции. Отрицательное
            значение по умолчанию означает: «клиент без тревожных сигналов
            считается лояльным».
        threshold: Порог классификации: probability >= threshold -> отток.
        expires_soon_days: Параметр N — окно в днях для признаков
            «услуга скоро истекает» и «ближайшие продления».

    Обоснование весов по умолчанию (экспертная оценка, шкала логита):
        - prolong_wait — сильнейший сигнал: клиент уже не оплатил услугу,
          и через 5 дней она будет удалена. Самый большой вес (+3.0).
        - prolong_wait_without_funds — усиливающий модификатор: ждёт оплаты,
          а денег нет даже с учётом бонусов (+2.0). В сумме с предыдущим
          даёт logit +5, что почти гарантированно классифицируется как отток.
        - failed_payment_ratio — доля неуспешных платежей, прямая история
          проблем с оплатой (+2.0 * ratio).
        - balance_deficit — ближайшие продления дороже доступных средств:
          физически не хватит денег продлить (+1.5).
        - autoprolong_off_ratio — клиент не доверяет автопродлению, каждое
          продление — ручное решение, где можно отказаться (+1.5 * ratio).
        - expires_soon_no_autoprolong — точка принятия решения уже близко,
          а автоматики нет (+1.2).
        - suspended_ratio — услуги уже приостановлены (обычно за неуплату),
          клиент частично «отвалился» (+1.0 * ratio).
        - deleted_blocked_ratio — клиент уже удалял услуги раньше,
          демонстрировал готовность расстаться с сервисами (+1.0 * ratio).
        - full_autoprolong_coverage — защитный признак: всё продлевается
          автоматически, клиент настроил и забыл (-1.0).
        - sufficient_funds — защитный признак: средств хватает на все
          ближайшие продления (-0.8).
    """

    weights: dict[str, float] = field(
        default_factory=lambda: {
            "has_prolong_wait": 3.0,
            "prolong_wait_without_funds": 2.0,
            "failed_payment_ratio": 2.0,
            "balance_deficit": 1.5,
            "autoprolong_off_ratio": 1.5,
            "expires_soon_no_autoprolong": 1.2,
            "suspended_ratio": 1.0,
            "deleted_blocked_ratio": 1.0,
            "full_autoprolong_coverage": -1.0,
            "sufficient_funds": -0.8,
        }
    )
    bias: float = -2.5
    threshold: float = 0.5
    expires_soon_days: int = DEFAULT_EXPIRES_SOON_DAYS

    def __post_init__(self) -> None:
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError("threshold должен быть в диапазоне [0, 1]")
        if self.expires_soon_days <= 0:
            raise ValueError("expires_soon_days должен быть положительным")


def _sigmoid(x: float) -> float:
    """Сигмоида с защитой от переполнения для больших по модулю значений."""
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    ex = math.exp(x)
    return ex / (1.0 + ex)


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


def extract_features(
    customer: dict[str, Any],
    config: ModelConfig,
    now: datetime | None = None,
) -> dict[str, float]:
    """Извлекает признаки из снапшота клиента.

    Все признаки приведены к диапазону [0, 1] (бинарные или доли),
    поэтому веса в конфиге напрямую сравнимы между собой и не требуют
    отдельной нормализации входных данных.

    Args:
        customer: JSON-снапшот клиента (аккаунт, услуги, транзакции).
        config: Конфигурация модели (нужен параметр expires_soon_days).
        now: Момент времени «сейчас»; по умолчанию — текущее UTC-время.
            Параметр вынесен для детерминированного тестирования.

    Returns:
        Словарь «имя признака -> значение».
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

    features: dict[str, float] = {}

    # --- prolong_wait: сильнейший сигнал оттока ---
    features["has_prolong_wait"] = 1.0 if prolong_wait_services else 0.0

    prolong_wait_cost = sum(float(s.get("price") or 0) for s in prolong_wait_services)
    features["prolong_wait_without_funds"] = (
        1.0 if prolong_wait_services and available_funds < prolong_wait_cost else 0.0
    )

    # --- активные услуги, истекающие в ближайшие N дней ---
    horizon_seconds = config.expires_soon_days * 86400
    expiring_soon = []
    for s in active_services:
        expires_at = _parse_datetime(s.get("expiresAt"))
        if expires_at is not None and 0 <= (expires_at - now).total_seconds() <= horizon_seconds:
            expiring_soon.append(s)

    features["expires_soon_no_autoprolong"] = (
        1.0 if any(not s.get("autoprolong") for s in expiring_soon) else 0.0
    )

    # --- баланс против ближайших продлений ---
    # «Ближайшие продления» = prolong_wait (уже ждут оплаты) + активные
    # услуги, истекающие в окне N дней.
    upcoming_cost = prolong_wait_cost + sum(float(s.get("price") or 0) for s in expiring_soon)
    features["balance_deficit"] = (
        1.0 if upcoming_cost > 0 and available_funds < upcoming_cost else 0.0
    )
    features["sufficient_funds"] = (
        1.0 if upcoming_cost > 0 and available_funds >= upcoming_cost else 0.0
    )

    # --- доли по услугам ---
    if active_services:
        features["autoprolong_off_ratio"] = (
            sum(1 for s in active_services if not s.get("autoprolong")) / len(active_services)
        )
    else:
        features["autoprolong_off_ratio"] = 0.0

    features["full_autoprolong_coverage"] = (
        1.0 if active_services and all(s.get("autoprolong") for s in active_services) else 0.0
    )

    total_services = len(services)
    features["suspended_ratio"] = len(suspended_services) / total_services if total_services else 0.0
    features["deleted_blocked_ratio"] = len(gone_services) / total_services if total_services else 0.0

    # --- история платежей ---
    total_tx = len(transactions)
    if total_tx:
        failed = sum(1 for t in transactions if t.get("status") == "not_performed")
        features["failed_payment_ratio"] = failed / total_tx
    else:
        features["failed_payment_ratio"] = 0.0

    return features


def _is_insufficient_data(customer: dict[str, Any]) -> bool:
    """Проверяет, достаточно ли данных для скоринга.

    Нет ни услуг, ни транзакций — оценивать нечего: любой вердикт
    был бы гаданием, поэтому возвращаем False (не отток) с флагом.
    """
    return not (customer.get("services") or []) and not (customer.get("transactions") or [])


def predict_churn_with_explanation(
    customer: dict[str, Any],
    config: ModelConfig | None = None,
    now: datetime | None = None,
) -> tuple[bool, float, dict[str, Any]]:
    """Предсказывает отток и возвращает разбор вкладов признаков.

    Args:
        customer: JSON-снапшот клиента.
        config: Конфигурация модели; при None используется конфиг по умолчанию.
        now: Момент «сейчас» (для тестов); по умолчанию текущее UTC-время.

    Returns:
        Кортеж (решение, вероятность, объяснение), где объяснение — dict:
        - contributions: вклад каждого признака в логит (weight * value);
        - bias: свободный член;
        - features: сырые значения признаков;
        - insufficient_data: True, если данных не хватило для оценки
          (тогда решение всегда False).
    """
    if config is None:
        config = ModelConfig()

    if _is_insufficient_data(customer):
        return False, 0.0, {
            "contributions": {},
            "bias": config.bias,
            "features": {},
            "insufficient_data": True,
        }

    features = extract_features(customer, config, now=now)

    contributions: dict[str, float] = {}
    logit = config.bias
    for name, weight in config.weights.items():
        # Признак из конфига, которого нет в extract_features, даёт нулевой
        # вклад — конфиг можно расширять заранее, не ломая старый код.
        value = features.get(name, 0.0)
        contribution = weight * value
        contributions[name] = contribution
        logit += contribution

    probability = _sigmoid(logit)
    decision = probability >= config.threshold

    return decision, probability, {
        "contributions": contributions,
        "bias": config.bias,
        "features": features,
        "insufficient_data": False,
    }


def predict_churn(
    customer: dict[str, Any],
    config: ModelConfig | None = None,
    now: datetime | None = None,
) -> bool:
    """Предсказывает, уйдёт ли клиент (не продлит услуги).

    Args:
        customer: JSON-снапшот клиента.
        config: Конфигурация модели; при None используется конфиг по умолчанию.
        now: Момент «сейчас» (для тестов); по умолчанию текущее UTC-время.

    Returns:
        True — клиент уйдёт (probability >= threshold), False — останется
        или данных недостаточно для оценки.
    """
    decision, _, _ = predict_churn_with_explanation(customer, config=config, now=now)
    return decision
