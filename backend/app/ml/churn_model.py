"""Модуль оценки риска оттока клиентов хостинг-платформы.

Исторических данных для обучения нет, поэтому используется логистическая
модель (weighted scoring):

    risk = sigmoid(w1*x1 + w2*x2 + ... + b)

Модель не классифицирует клиента («уйдёт/останется»), а возвращает оценку
риска ухода — целое число от 0 до 100 (``round(probability * 100)``).

Веса признаков не зашиты в код: пользователь обязан передать их сам через
``ModelConfig(weights={...})`` — у ``weights`` нет значения по умолчанию.
Сами признаки — реестр в ``app.ml.features`` (``FEATURE_REGISTRY``): чтобы
добавить новый, достаточно одного нового файла там, здесь ничего не меняется.

Зависимости: только стандартная библиотека (Python 3.11+).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.ml.features import FEATURE_REGISTRY, build_context

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


def extract_features(
    customer: dict[str, Any],
    config: ModelConfig,
    now: datetime | None = None,
) -> dict[str, float]:
    """Извлекает признаки из снапшота клиента через реестр (app/ml/features).

    Все признаки приведены к диапазону [0, 1] (бинарные или доли),
    поэтому веса в конфиге напрямую сравнимы между собой и не требуют
    отдельной нормализации входных данных.

    Args:
        customer: JSON-снапшот клиента (аккаунт, услуги, транзакции).
        config: Конфигурация модели (нужен параметр expires_soon_days).
        now: Момент времени «сейчас»; по умолчанию — текущее UTC-время.
            Параметр вынесен для детерминированного тестирования.

    Returns:
        Словарь «код признака -> значение».
    """
    ctx = build_context(customer, config.expires_soon_days, now)
    return {feature.code: feature.value(ctx) for feature in FEATURE_REGISTRY}


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
