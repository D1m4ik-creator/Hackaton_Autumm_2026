"""Адаптер модуля анализа к логистической модели оттока (``app.ml.churn_model``).

Реализует три функции контракта ``app.analysis`` (см. ``app/analysis/types.py``):

* ``default_settings()`` — настройки по умолчанию (JSON-сериализуемые);
* ``validate_settings(data)`` — нормализация с понятными ошибками на русском;
* ``analyze(source, settings, as_of)`` — оценка риска по всем клиентам.

Модель — ``predict_churn_score_with_explanation``; веса ей задаёт
пользователь через настройки (у самой модели весов по умолчанию нет).
Веса и тексты причин по умолчанию выводятся из реестра признаков
``app.ml.features.FEATURE_REGISTRY`` и отдаются через ``default_settings()``.
Адаптер готовит для модели снимок каждого клиента, переводит её ``score``
0..100 в уровень ``high/medium/low``, считает денежную оценку потерь и
собирает причины.

Исправления на границе данных и модели (баги в данных, а не в модели):

* поле услуги в данных называется ``autoProlong`` (``ServiceData.auto_prolong``),
  а модель читает ключ ``autoprolong`` — адаптер кладёт значение под нужным ключом;
* ``bonusState`` в данных — строка ``"locked"``/``"unlocked"``, а модель делает
  ``bool(...)``; адаптер передаёт ``True`` только при ``"unlocked"``.

Как добавить признак: создать ``Feature`` в новом файле
``app/ml/features/<имя>.py`` (код, вес по умолчанию, текст причины, функция
``compute(ctx) -> float в [0,1]``) и добавить его в ``FEATURE_REGISTRY``
(``app/ml/features/__init__.py``) — вес и текст причины подхватятся сюда
автоматически, больше ничего в адаптере или модели менять не нужно.

Признак, у которого есть вес, но нет записи в реестре (например, старое имя
после удаления файла), даёт нулевой вклад (модель берёт
``features.get(name, 0.0)``) и не падает; для него показывается общая подпись
«Признак «имя»» (см. ``_reason_text`` ниже).
"""

from __future__ import annotations

import math
import re
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
from app.ml.features import FEATURE_REGISTRY
from app.ml.features.custom import make_custom_feature, validate_formula

# Коды пользовательских метрик: как имена переменных Python, не пересекаются
# с кодами встроенных признаков (зарезервированы).
_CUSTOM_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,40}$")
_BUILTIN_CODES = frozenset(feature.code for feature in FEATURE_REGISTRY)

# Веса и тексты причин по умолчанию выводятся из реестра признаков
# (app/ml/features) — у каждого Feature вес и текст объяснения уже заданы
# рядом с его формулой, здесь их незачем дублировать вручную (раньше это
# были два отдельных литерала, которые нужно было синхронизировать руками
# при каждом новом признаке — источник рассинхрона).
_DEFAULT_WEIGHTS: dict[str, float] = {feature.code: feature.default_weight for feature in FEATURE_REGISTRY}

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

# Человеко-читаемые причины по кодам признаков — тоже из реестра.
_REASON_TEXTS: dict[str, str] = {feature.code: feature.reason_text for feature in FEATURE_REGISTRY}


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
        "customFeatures": {},
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

    if "customFeatures" in data:
        custom_features = data["customFeatures"]
        if not isinstance(custom_features, dict):
            raise ValueError("customFeatures должен быть объектом {код метрики: {label, formula}}")
        normalized_custom: dict[str, dict[str, str]] = {}
        for code, spec in custom_features.items():
            if not isinstance(code, str) or not _CUSTOM_CODE_PATTERN.match(code):
                raise ValueError(
                    f"код метрики {code!r} должен состоять из латиницы в нижнем регистре, "
                    "цифр и подчёркиваний, начинаться с буквы, длина 3-41 символ"
                )
            if code in _BUILTIN_CODES:
                raise ValueError(f"код метрики {code!r} зарезервирован встроенным признаком")
            if not isinstance(spec, dict):
                raise ValueError(f"метрика {code!r} должна быть объектом {{label, formula}}")
            label = spec.get("label")
            if not isinstance(label, str) or not label.strip():
                raise ValueError(f"метрика {code!r}: label должен быть непустой строкой")
            formula = spec.get("formula")
            if not isinstance(formula, str) or not formula.strip():
                raise ValueError(f"метрика {code!r}: formula должна быть непустой строкой")
            validate_formula(formula)
            normalized_custom[code] = {"label": label, "formula": formula}
        result["customFeatures"] = normalized_custom

    return result


def _reason_text(name: str, reason_texts: dict[str, str]) -> str:
    """Текст причины по имени признака; для неизвестного — «Признак «имя»»."""
    return reason_texts.get(name, f"Признак «{name}»")


def _build_reasons(contributions: dict[str, float], reason_texts: dict[str, str]) -> list[Reason]:
    """Причины: положительные вклады по убыванию, максимум 3."""
    positive = sorted(
        ((name, value) for name, value in contributions.items() if value > 0),
        key=lambda item: item[1],
        reverse=True,
    )
    reasons = [Reason(name, _reason_text(name, reason_texts)) for name, _ in positive[:3]]
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
    # Пустой weights={} — все признаки удалены (score только по bias), а не «настроек нет»
    weights = settings.get("weights")
    if weights is None:
        weights = dict(_DEFAULT_WEIGHTS)
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

    # Пользовательские метрики по формуле (admin/superadmin, см.
    # app/ml/features/custom.py) — считаются наравне со встроенными, их
    # тексты причин объединяем с дефолтными локально для этого вызова.
    custom_specs = settings.get("customFeatures") or {}
    extra_features = [
        make_custom_feature(code, spec["label"], spec["formula"])
        for code, spec in custom_specs.items()
    ]
    reason_texts = {**_REASON_TEXTS, **{code: spec["label"] for code, spec in custom_specs.items()}}

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
            # Только для признака customer_value (app/ml/features/customer_value.py) —
            # остальные признаки на сумму пополнений не смотрят.
            "totalReplenished": account.total_replenished,
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
            customer, config, now=as_of, extra_features=extra_features
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
                reasons=_build_reasons(contributions, reason_texts),
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
