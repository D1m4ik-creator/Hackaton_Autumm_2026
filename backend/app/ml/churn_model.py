"""Модуль оценки риска оттока клиентов хостинг-платформы.

Исторических данных для обучения нет, поэтому используется логистическая
модель (weighted scoring):

    risk = sigmoid(w1*x1 + w2*x2 + ... + b)

Модель не классифицирует клиента («уйдёт/останется»), а возвращает оценку
риска ухода — целое число от 0 до 100 (``round(probability * 100)``).

Веса признаков не зашиты в код: пользователь обязан передать их сам через
``ModelConfig(weights={...})`` — у ``weights`` нет значения по умолчанию.
Чтобы добавить признак, достаточно вычислить его в ``extract_features`` и
добавить его вес в передаваемый словарь.

Зависимости: только стандартная библиотека (Python 3.11+).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

# Статусы услуг, которые считаются «живыми» и участвуют в оценке
# будущего оттока. deleted/blocked — уже свершившийся факт, они
# учитываются только как исторический признак (deleted_blocked_ratio).
ACTIVE_STATUSES = frozenset({"active", "prolong_wait"})

# Горизонт «ближайших продлений» по умолчанию (дней), если не задан в конфиге.
DEFAULT_EXPIRES_SOON_DAYS = 7


def _is_finite_number(value: Any) -> bool:
    """Конечное число (int или float), но не bool."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


@dataclass
class ModelConfig:
    """Конфигурация модели оттока.

    Attributes:
        weights: Отображение «имя признака -> вес». Обязательный параметр:
            веса задаёт пользователь модели, значения по умолчанию нет.
            Признак, отсутствующий в словаре, просто не участвует в
            скоринге — так новый признак добавляется одной строкой.
        bias: Свободный член (b) логистической функции. По умолчанию 0:
            клиент без сигналов получает нейтральную оценку 50; отрицательное
            значение смещает базовую оценку в сторону «лоялен».
        expires_soon_days: Параметр N — окно в днях для признаков
            «услуга скоро истекает» и «ближайшие продления».
    """

    weights: dict[str, float]
    bias: float = 0.0
    expires_soon_days: int = DEFAULT_EXPIRES_SOON_DAYS

    def __post_init__(self) -> None:
        if not isinstance(self.weights, dict):
            raise ValueError("weights должен быть словарём {имя признака: вес}")
        for name, weight in self.weights.items():
            if not isinstance(name, str):
                raise ValueError("имена признаков в weights должны быть строками")
            if not _is_finite_number(weight):
                raise ValueError(f"вес признака {name!r} должен быть конечным числом")
        if not _is_finite_number(self.bias):
            raise ValueError("bias должен быть конечным числом")
        if self.expires_soon_days <= 0:
            raise ValueError("expires_soon_days должен быть положительным")


def _sigmoid(x: float) -> float:
    """Сигмоида с защитой от переполнения для больших по модулю значений."""
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    ex = math.exp(x)
    return ex / (1.0 + ex)


def _score_from_probability(probability: float) -> int:
    """Переводит вероятность оттока в целую оценку риска 0..100."""
    return max(0, min(100, round(probability * 100)))


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

    Нет ни услуг, ни транзакций — оценивать нечего: любая оценка была бы
    гаданием, поэтому возвращаем None с флагом insufficient_data.
    """
    return not (customer.get("services") or []) and not (customer.get("transactions") or [])


def predict_churn_score_with_explanation(
    customer: dict[str, Any],
    config: ModelConfig,
    now: datetime | None = None,
) -> tuple[int | None, float, dict[str, Any]]:
    """Оценивает риск оттока и возвращает разбор вкладов признаков.

    Args:
        customer: JSON-снапшот клиента.
        config: Конфигурация модели с заданными пользователем весами.
        now: Момент «сейчас» (для тестов); по умолчанию текущее UTC-время.

    Returns:
        Кортеж (оценка, вероятность, объяснение), где:
        - оценка — целое число 0..100 (риск ухода) либо None, если данных
          недостаточно для оценки;
        - вероятность — сырое значение sigmoid в диапазоне [0, 1];
        - объяснение — dict:
            - contributions: вклад каждого признака в логит (weight * value);
            - bias: свободный член;
            - features: сырые значения признаков;
            - insufficient_data: True, если данных не хватило для оценки
              (тогда оценка — None, вероятность — 0.0).
    """
    if _is_insufficient_data(customer):
        return None, 0.0, {
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
    score = _score_from_probability(probability)

    return score, probability, {
        "contributions": contributions,
        "bias": config.bias,
        "features": features,
        "insufficient_data": False,
    }


def predict_churn_score(
    customer: dict[str, Any],
    config: ModelConfig,
    now: datetime | None = None,
) -> int | None:
    """Оценивает риск оттока клиента по шкале 0..100.

    Args:
        customer: JSON-снапшот клиента.
        config: Конфигурация модели с заданными пользователем весами.
        now: Момент «сейчас» (для тестов); по умолчанию текущее UTC-время.

    Returns:
        Целое число от 0 до 100 — оценка риска ухода (0 — точно останется,
        100 — точно уйдёт). None — данных недостаточно для оценки.
    """
    score, _, _ = predict_churn_score_with_explanation(customer, config, now=now)
    return score
