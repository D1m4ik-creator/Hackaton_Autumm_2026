"""Адаптер модуля анализа к логистической модели оттока (``app.ml.churn_model``).

Реализует три функции контракта ``app.analysis`` (см. ``app/analysis/types.py``):

* ``default_settings()`` — настройки по умолчанию (JSON-сериализуемые);
* ``validate_settings(data)`` — нормализация с понятными ошибками на русском;
* ``analyze(source, settings, as_of)`` — оценка риска по всем клиентам.

Модель — ``predict_churn_score_with_explanation``; веса ей задаёт
пользователь через настройки (у самой модели весов по умолчанию нет).
Экспертные веса по умолчанию живут здесь, в ``_DEFAULT_WEIGHTS``, и отдаются
через ``default_settings()``. Адаптер готовит для модели снимок каждого
клиента, переводит её ``score`` 0..100 в уровень ``high/medium/low``, считает
денежную оценку потерь и собирает причины.

Исправления на границе данных и модели (баги в данных, а не в модели):

* поле услуги в данных называется ``autoProlong`` (``ServiceData.auto_prolong``),
  а модель читает ключ ``autoprolong`` — адаптер кладёт значение под нужным ключом;
* ``bonusState`` в данных — строка ``"locked"``/``"unlocked"``, а модель делает
  ``bool(...)``; адаптер передаёт ``True`` только при ``"unlocked"``.

Как добавить признак (расширяемость без правки инфраструктуры):

1. вычислить признак в ``app.ml.churn_model.extract_features`` (значение в [0, 1]);
2. добавить его вес в ``weights`` — через ``default_settings()`` или через
   сохранённые настройки (``PATCH /model/settings``).

Признак, у которого есть вес, но нет реализации в ``extract_features``, даёт
нулевой вклад (модель берёт ``features.get(name, 0.0)``), поэтому вес можно
завести заранее. Текст причины для нового признака добавляется в
``_REASON_TEXTS`` ниже; для неизвестного имени показывается «Признак «имя»».
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from app.analysis.types import (
    AnalysisResult,
    CustomerRisk,
    Reason,
    ServiceData,
    SourceData,
)
from app.ml.churn_model import (
    DEFAULT_EXPIRES_SOON_DAYS,
    ModelConfig,
    predict_churn_score_with_explanation,
)

# Веса признаков по умолчанию (экспертная оценка, шкала логита). Модель сама
# весов не задаёт — их передаёт пользователь через настройки; эти значения
# адаптер отдаёт в ``default_settings()`` как стартовую точку.
# Обоснование:
#   - prolong_wait — сильнейший сигнал: клиент уже не оплатил услугу,
#     и через 5 дней она будет удалена. Самый большой вес (+3.0).
#   - prolong_wait_without_funds — усиливающий модификатор: ждёт оплаты,
#     а денег нет даже с учётом бонусов (+2.0). В сумме с предыдущим
#     даёт logit +5, что даёт оценку риска около 99.
#   - failed_payment_ratio — доля неуспешных платежей, прямая история
#     проблем с оплатой (+2.0 * ratio).
#   - balance_deficit — ближайшие продления дороже доступных средств:
#     физически не хватит денег продлить (+1.5).
#   - autoprolong_off_ratio — клиент не доверяет автопродлению, каждое
#     продление — ручное решение, где можно отказаться (+1.5 * ratio).
#   - expires_soon_no_autoprolong — точка принятия решения уже близко,
#     а автоматики нет (+1.2).
#   - suspended_ratio — услуги уже приостановлены (обычно за неуплату),
#     клиент частично «отвалился» (+1.0 * ratio).
#   - deleted_blocked_ratio — клиент уже удалял услуги раньше,
#     демонстрировал готовность расстаться с сервисами (+1.0 * ratio).
#   - full_autoprolong_coverage — защитный признак: всё продлевается
#     автоматически, клиент настроил и забыл (-1.0).
#   - sufficient_funds — защитный признак: средств хватает на все
#     ближайшие продления (-0.8).
_DEFAULT_WEIGHTS: dict[str, float] = {
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

# Свободный член по умолчанию: отрицательное значение означает «клиент без
# тревожных сигналов считается лояльным».
_DEFAULT_BIAS = -2.5

# Уровни порогов по score 0..100 по умолчанию.
_DEFAULT_THRESHOLDS = {"high": 70, "medium": 35}

# Горизонт денежной оценки по умолчанию (дней).
_DEFAULT_HORIZON_DAYS = 30

# Статусы услуг, которые приносят выручку и потому участвуют в оценке потерь.
# deleted/blocked — уже свершившийся уход, выручки не дают.
_LIVE_FOR_LOSS = frozenset({"active", "prolong_wait", "suspended"})

# Длительность одного оплачиваемого периода в днях для расчёта числа оплат.
_PERIOD_DAYS: dict[str, float] = {
    "hour": 1 / 24,
    "week": 7,
    "month": 30,
    "quarter_year": 91,
    "half_year": 182,
    "year": 365,
}

# Человеко-читаемые причины по именам признаков.
_REASON_TEXTS: dict[str, str] = {
    "has_prolong_wait": "Есть услуга в статусе «Ожидает оплаты»",
    "prolong_wait_without_funds": "Ожидает оплаты, а денег на счёте не хватает",
    "failed_payment_ratio": "Много неуспешных платежей",
    "balance_deficit": "Баланса не хватает на ближайшие продления",
    "autoprolong_off_ratio": "У активных услуг выключено автопродление",
    "expires_soon_no_autoprolong": "Услуга скоро истекает, автопродление выключено",
    "suspended_ratio": "Часть услуг приостановлена",
    "deleted_blocked_ratio": "Раньше удалял или потерял услуги",
    "full_autoprolong_coverage": "Всё продлевается автоматически",
    "sufficient_funds": "Средств хватает на ближайшие продления",
}


def _is_number(value: Any) -> bool:
    """Конечное число (int или float), но не bool."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _is_int(value: Any) -> bool:
    """Целое число, но не bool."""
    return isinstance(value, int) and not isinstance(value, bool)


def _iso(dt: datetime | None) -> str | None:
    """Дата в ISO-строку UTC; наивную дату трактуем как UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def default_settings() -> dict:
    """Настройки по умолчанию (JSON-сериализуемые).

    ``weights`` и ``bias`` берутся из ``_DEFAULT_WEIGHTS``/``_DEFAULT_BIAS`` —
    единого источника правды по коэффициентам модели на уровне приложения
    (сама модель весов по умолчанию не имеет, их задаёт пользователь).
    """
    return {
        "asOf": None,
        "weights": dict(_DEFAULT_WEIGHTS),
        "bias": _DEFAULT_BIAS,
        "thresholds": dict(_DEFAULT_THRESHOLDS),
        "expiresSoonDays": DEFAULT_EXPIRES_SOON_DAYS,
        "horizonDays": _DEFAULT_HORIZON_DAYS,
    }


def validate_settings(data: dict) -> dict:
    """Нормализует настройки; при ошибке — ``ValueError`` с понятным текстом.

    Проверяются только присутствующие ключи (эффективные настройки —
    deep-merge дефолтов и сохранённого, поэтому отсутствие ключа безопасно).
    Неизвестные ключи верхнего уровня сохраняются как есть — так новый
    коэффициент добавляется без правки инфраструктуры.
    """
    if not isinstance(data, dict):
        raise ValueError("Настройки должны быть объектом JSON")
    result = dict(data)

    if "asOf" in data:
        as_of = data["asOf"]
        if as_of is not None:
            if not isinstance(as_of, str):
                raise ValueError("asOf должен быть строкой ISO-8601 или null")
            try:
                datetime.fromisoformat(as_of.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError(f"asOf не является датой ISO-8601: {as_of!r}") from exc
        result["asOf"] = as_of

    if "weights" in data:
        weights = data["weights"]
        if not isinstance(weights, dict):
            raise ValueError("weights должен быть объектом вида {имя признака: число}")
        normalized: dict[str, float] = {}
        for name, weight in weights.items():
            if not isinstance(name, str):
                raise ValueError("имена признаков в weights должны быть строками")
            if not _is_number(weight):
                raise ValueError(f"вес признака {name!r} должен быть конечным числом")
            normalized[name] = float(weight)
        result["weights"] = normalized

    if "bias" in data:
        if not _is_number(data["bias"]):
            raise ValueError("bias должен быть конечным числом")
        result["bias"] = float(data["bias"])

    if "thresholds" in data:
        thresholds = data["thresholds"]
        if not isinstance(thresholds, dict):
            raise ValueError("thresholds должен быть объектом с ключами high и medium")
        if "high" not in thresholds or "medium" not in thresholds:
            raise ValueError("thresholds должен содержать ключи high и medium")
        high, medium = thresholds["high"], thresholds["medium"]
        if not _is_number(high) or not _is_number(medium):
            raise ValueError("пороги уровней high и medium должны быть числами")
        high, medium = float(high), float(medium)
        if not (0.0 <= medium < high <= 100.0):
            raise ValueError(
                "пороги уровней должны удовлетворять условию 0 <= medium < high <= 100"
            )
        normalized_th = dict(thresholds)
        normalized_th["high"] = high
        normalized_th["medium"] = medium
        result["thresholds"] = normalized_th

    if "expiresSoonDays" in data:
        value = data["expiresSoonDays"]
        if not _is_int(value) or not (1 <= value <= 365):
            raise ValueError("expiresSoonDays должен быть целым числом от 1 до 365")
        result["expiresSoonDays"] = value

    if "horizonDays" in data:
        value = data["horizonDays"]
        if not _is_int(value) or not (1 <= value <= 3650):
            raise ValueError("horizonDays должен быть целым числом от 1 до 3650")
        result["horizonDays"] = value

    return result


def _reason_text(name: str) -> str:
    """Текст причины по имени признака; для неизвестного — «Признак «имя»»."""
    return _REASON_TEXTS.get(name, f"Признак «{name}»")


def _build_reasons(contributions: dict[str, float]) -> list[Reason]:
    """Причины: положительные вклады по убыванию, максимум 3."""
    positive = sorted(
        ((name, value) for name, value in contributions.items() if value > 0),
        key=lambda item: item[1],
        reverse=True,
    )
    reasons = [Reason(name, _reason_text(name)) for name, _ in positive[:3]]
    if not reasons:
        return [Reason("no_risk_signals", "Тревожных сигналов не найдено")]
    return reasons


def _expected_loss_cents(
    services: list[ServiceData], probability: float, horizon_days: int
) -> int:
    """Ожидаемые потери: вероятность оттока × выручка «живых» услуг за горизонт.

    Выручка услуги = ``price`` × число оплат за горизонт, где число оплат =
    ``max(1, floor(horizon_days / дней_в_периоде))``. Неизвестный период
    считается как одна оплата за горизонт.
    """
    revenue = 0.0
    for service in services:
        if service.status not in _LIVE_FOR_LOSS:
            continue
        period_days = _PERIOD_DAYS.get(service.payment_term)
        if period_days is None or period_days <= 0:
            payments = 1
        else:
            payments = max(1, math.floor(horizon_days / period_days))
        revenue += service.price * payments
    return max(0, round(probability * revenue))


def analyze(source: SourceData, settings: dict, as_of: datetime) -> AnalysisResult:
    """Оценивает риск оттока по каждому клиенту снимка.

    ``settings`` уже прошёл ``validate_settings`` (гарантия инфраструктуры);
    отсутствующие ключи подставляются из дефолтов адаптера.
    """
    weights = settings.get("weights") or dict(_DEFAULT_WEIGHTS)
    bias = settings.get("bias", _DEFAULT_BIAS)
    expires_soon_days = settings.get("expiresSoonDays", DEFAULT_EXPIRES_SOON_DAYS)
    horizon_days = int(settings.get("horizonDays", _DEFAULT_HORIZON_DAYS))
    thresholds = settings.get("thresholds") or _DEFAULT_THRESHOLDS
    high_threshold = float(thresholds.get("high", _DEFAULT_THRESHOLDS["high"]))
    medium_threshold = float(thresholds.get("medium", _DEFAULT_THRESHOLDS["medium"]))

    config = ModelConfig(
        weights=dict(weights),
        bias=float(bias),
        expires_soon_days=int(expires_soon_days),
    )

    # Группировка без N+1: услуги по владельцу, транзакции по владельцу услуги.
    services_by_owner: dict[int, list[ServiceData]] = defaultdict(list)
    service_owner: dict[int, int] = {}
    for service in source.services:
        services_by_owner[service.owner_id].append(service)
        service_owner[service.id] = service.owner_id

    transactions_by_owner: dict[int, list[Any]] = defaultdict(list)
    for transaction in source.transactions:
        owner_id = service_owner.get(transaction.service_id)
        if owner_id is not None:
            transactions_by_owner[owner_id].append(transaction)

    customers: list[CustomerRisk] = []
    for account in source.accounts:
        account_services = services_by_owner.get(account.id, [])
        account_transactions = transactions_by_owner.get(account.id, [])

        # bonusState в данных — строка; доступ к бонусам только при "unlocked".
        customer: dict[str, Any] = {
            "id": account.id,
            "balance": account.balance,
            "bonusBalance": account.bonus_balance,
            "bonusState": account.bonus_state == "unlocked",
            "services": [
                {
                    "status": service.status,
                    "price": service.price,
                    "expiresAt": _iso(service.expires_at),
                    # autoProlong в данных -> autoprolong для модели
                    "autoprolong": service.auto_prolong,
                }
                for service in account_services
            ],
            "transactions": [
                {"status": transaction.status} for transaction in account_transactions
            ],
        }

        score, probability, explanation = predict_churn_score_with_explanation(
            customer, config, now=as_of
        )

        live_services = sum(
            1 for service in account_services if service.status in _LIVE_FOR_LOSS
        )

        if explanation.get("insufficient_data"):
            customers.append(
                CustomerRisk(
                    account_id=account.id,
                    score=None,
                    level="no_data",
                    reasons=[Reason("no_data", "Недостаточно данных для оценки")],
                    expected_loss_cents=0,
                    details={
                        "probability": 0.0,
                        "features": {},
                        "contributions": {},
                        "bias": float(explanation.get("bias", config.bias)),
                        "liveServices": live_services,
                        "horizonDays": horizon_days,
                    },
                )
            )
            continue

        # Оценку 0..100 уже посчитала модель; здесь только уровень по порогам.
        assert score is not None  # ветка insufficient_data обработана выше
        if score >= high_threshold:
            level = "high"
        elif score >= medium_threshold:
            level = "medium"
        else:
            level = "low"

        contributions = {
            name: float(value) for name, value in explanation["contributions"].items()
        }
        features = {
            name: float(value) for name, value in explanation["features"].items()
        }

        customers.append(
            CustomerRisk(
                account_id=account.id,
                score=score,
                level=level,
                reasons=_build_reasons(contributions),
                expected_loss_cents=_expected_loss_cents(
                    account_services, probability, horizon_days
                ),
                details={
                    "probability": float(probability),
                    "features": features,
                    "contributions": contributions,
                    "bias": float(explanation.get("bias", config.bias)),
                    "liveServices": live_services,
                    "horizonDays": horizon_days,
                },
            )
        )

    loss_explanation = (
        f"Ожидаемые потери за {horizon_days} дней: вероятность оттока клиента, "
        "умноженная на выручку от его действующих услуг (active, prolong_wait, "
        "suspended) за этот период. Суммы в евроцентах. "
        f"Оценка на момент asOf = {as_of.isoformat()}."
    )
    return AnalysisResult(customers=customers, loss_explanation=loss_explanation)
