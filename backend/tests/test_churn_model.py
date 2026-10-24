"""Юнит-тесты для churn_model (pytest).

Модель возвращает оценку риска оттока 0..100 (или None, если данных мало),
а веса признаков всегда задаёт пользователь через ``ModelConfig.weights`` —
значений по умолчанию у модели нет. Поэтому каждый тест передаёт свои веса.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.ml.churn_model import (
    ModelConfig,
    extract_features,
    predict_churn_score,
    predict_churn_score_with_explanation,
)

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

# Пользовательские веса для тестов (экспертная оценка в шкале логита).
WEIGHTS: dict[str, float] = {
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
BIAS = -2.5


def _config(weights: dict[str, float] | None = None, bias: float = BIAS) -> ModelConfig:
    """Конфиг с пользовательскими весами (по умолчанию — тестовый набор)."""
    return ModelConfig(weights=dict(WEIGHTS) if weights is None else weights, bias=bias)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def test_prolong_wait_without_funds_gives_high_score() -> None:
    """Клиент с услугой в prolong_wait и пустым балансом -> высокий риск."""
    customer = {
        "balance": 0,
        "withdrawBalance": 0,
        "bonusBalance": 0,
        "bonusState": False,
        "totalReplenished": 500,
        "services": [
            {
                "name": "vds-1",
                "price": 5000,
                "status": "prolong_wait",
                "autoprolong": False,
                "paymentTerm": "month",
                "expiresAt": _iso(NOW - timedelta(days=1)),
            }
        ],
        "transactions": [
            {"status": "performed", "type": "order", "amount": 5000},
        ],
    }
    score, probability, explanation = predict_churn_score_with_explanation(
        customer, _config(), now=NOW
    )

    # logit = -2.5 + 3.0 (prolong_wait) + 2.0 (без средств) + 1.5 (дефицит) = 4.0
    assert score == 98
    assert isinstance(score, int)
    assert 0.95 <= probability <= 1.0
    assert explanation["insufficient_data"] is False
    # Оба ключевых сигнала должны дать положительный вклад.
    assert explanation["contributions"]["has_prolong_wait"] > 0
    assert explanation["contributions"]["prolong_wait_without_funds"] > 0
    # predict_churn_score возвращает ту же оценку.
    assert predict_churn_score(customer, _config(), now=NOW) == score


def test_loyal_customer_with_autoprolong_and_money_gets_low_score() -> None:
    """Автопродление + большой баланс -> низкий риск."""
    customer = {
        "balance": 100_000,
        "withdrawBalance": 0,
        "bonusBalance": 10_000,
        "bonusState": True,
        "totalReplenished": 500_000,
        "services": [
            {
                "name": "vds-1",
                "price": 5000,
                "status": "active",
                "autoprolong": True,
                "paymentTerm": "month",
                "expiresAt": _iso(NOW + timedelta(days=3)),
            },
            {
                "name": "domain-1",
                "price": 1000,
                "status": "active",
                "autoprolong": True,
                "paymentTerm": "year",
                "expiresAt": _iso(NOW + timedelta(days=200)),
            },
        ],
        "transactions": [
            {"status": "performed", "type": "prolong", "amount": 5000},
            {"status": "performed", "type": "prolong", "amount": 1000},
        ],
    }
    score, probability, explanation = predict_churn_score_with_explanation(
        customer, _config(), now=NOW
    )

    # logit = -2.5 - 1.0 (полное автопродление) - 0.8 (средств хватает) = -4.3
    assert score == 1
    assert probability < 0.05
    # Защитные признаки сработали.
    assert explanation["features"]["full_autoprolong_coverage"] == 1.0
    assert explanation["features"]["sufficient_funds"] == 1.0


def test_empty_customer_returns_none_and_flags_insufficient_data() -> None:
    """Пустые данные -> без исключений, оценка None, флаг insufficient_data."""
    for customer in ({}, {"services": [], "transactions": []}):
        score, probability, explanation = predict_churn_score_with_explanation(
            customer, _config(), now=NOW
        )
        assert score is None
        assert probability == 0.0
        assert explanation["insufficient_data"] is True
        assert predict_churn_score(customer, _config(), now=NOW) is None


def test_no_transactions_is_not_insufficient_if_services_exist() -> None:
    """Услуги есть, транзакций нет -> считаем, failed_payment_ratio = 0."""
    customer = {
        "balance": 100_000,
        "bonusState": False,
        "services": [
            {
                "name": "vds-1",
                "price": 5000,
                "status": "active",
                "autoprolong": True,
                "paymentTerm": "month",
                "expiresAt": _iso(NOW + timedelta(days=30)),
            }
        ],
        "transactions": [],
    }
    score, _, explanation = predict_churn_score_with_explanation(customer, _config(), now=NOW)
    assert score is not None
    assert score < 35
    assert explanation["insufficient_data"] is False
    assert explanation["features"]["failed_payment_ratio"] == 0.0


def test_failed_payments_and_no_autoprolong_raise_score() -> None:
    """Много неуспешных платежей + ручные продления -> риск выше, чем у чистого клиента."""
    risky = {
        "balance": 100,
        "bonusState": False,
        "services": [
            {
                "name": "vds-1",
                "price": 5000,
                "status": "active",
                "autoprolong": False,
                "paymentTerm": "month",
                "expiresAt": _iso(NOW + timedelta(days=2)),
            }
        ],
        "transactions": [
            {"status": "not_performed", "type": "prolong", "amount": 5000},
            {"status": "not_performed", "type": "prolong", "amount": 5000},
            {"status": "performed", "type": "order", "amount": 5000},
        ],
    }
    clean = {
        **risky,
        "balance": 100_000,
        "services": [{**risky["services"][0], "autoprolong": True}],
        "transactions": [
            {"status": "performed", "type": "prolong", "amount": 5000},
            {"status": "performed", "type": "prolong", "amount": 5000},
            {"status": "performed", "type": "order", "amount": 5000},
        ],
    }
    risky_score, _, risky_explanation = predict_churn_score_with_explanation(
        risky, _config(), now=NOW
    )
    clean_score, _, _ = predict_churn_score_with_explanation(clean, _config(), now=NOW)

    assert risky_explanation["features"]["failed_payment_ratio"] == 2 / 3
    assert risky_explanation["features"]["expires_soon_no_autoprolong"] == 1.0
    assert risky_explanation["features"]["balance_deficit"] == 1.0
    assert risky_score is not None and clean_score is not None
    assert risky_score > clean_score


def test_deleted_services_are_history_not_future_churn() -> None:
    """deleted/blocked не создают сигналы будущего оттока, только долю в истории."""
    customer = {
        "balance": 50_000,
        "bonusState": False,
        "services": [
            {
                "name": "old-vds",
                "price": 5000,
                "status": "deleted",
                "autoprolong": False,
                "paymentTerm": "month",
                "expiresAt": _iso(NOW - timedelta(days=30)),
            }
        ],
        "transactions": [
            {"status": "performed", "type": "prolong", "amount": 5000},
        ],
    }
    score, _, explanation = predict_churn_score_with_explanation(customer, _config(), now=NOW)

    assert score is not None and score < 50
    assert explanation["features"]["has_prolong_wait"] == 0.0
    assert explanation["features"]["expires_soon_no_autoprolong"] == 0.0
    assert explanation["features"]["balance_deficit"] == 0.0
    # Но факт удаления зафиксирован как признак.
    assert explanation["features"]["deleted_blocked_ratio"] == 1.0


def test_bonus_balance_counts_only_when_bonus_state_enabled() -> None:
    """Бонусы покрывают дефицит только при bonusState=True."""
    base = {
        "balance": 0,
        "bonusBalance": 6000,
        "transactions": [{"status": "performed", "type": "order", "amount": 100}],
        "services": [
            {
                "name": "vds-1",
                "price": 5000,
                "status": "active",
                "autoprolong": True,
                "paymentTerm": "month",
                "expiresAt": _iso(NOW + timedelta(days=3)),
            }
        ],
    }
    with_bonus = extract_features({**base, "bonusState": True}, _config(), now=NOW)
    without_bonus = extract_features({**base, "bonusState": False}, _config(), now=NOW)

    assert with_bonus["balance_deficit"] == 0.0
    assert without_bonus["balance_deficit"] == 1.0


def test_weights_are_mandatory() -> None:
    """Веса задаёт пользователь: ModelConfig без weights не создаётся."""
    with pytest.raises(TypeError):
        ModelConfig()  # type: ignore[call-arg]


def test_user_weights_change_the_score() -> None:
    """Один и тот же клиент получает разную оценку при разных весах."""
    customer = {
        "balance": 0,
        "bonusState": False,
        "services": [
            {
                "name": "vds-1",
                "price": 5000,
                "status": "prolong_wait",
                "autoprolong": False,
                "paymentTerm": "month",
                "expiresAt": _iso(NOW - timedelta(days=1)),
            }
        ],
        "transactions": [],
    }
    strong = predict_churn_score(customer, _config({"has_prolong_wait": 3.0}), now=NOW)
    weak = predict_churn_score(customer, _config({"has_prolong_wait": 0.5}), now=NOW)
    assert strong is not None and weak is not None
    assert strong > weak

    # Нулевые веса -> оценка определяется только bias: sigmoid(-2.5) * 100 = 8.
    neutral = predict_churn_score(customer, _config({}, bias=-2.5), now=NOW)
    assert neutral == 8

    # Нулевые веса и нулевой bias -> нейтральные 50.
    fifty = predict_churn_score(customer, _config({}, bias=0.0), now=NOW)
    assert fifty == 50


def test_score_stays_within_0_100_for_extreme_weights() -> None:
    """Сигмоида насыщается: экстремальные веса не выводят оценку за 0..100."""
    customer = {
        "balance": 0,
        "bonusState": False,
        "services": [
            {
                "name": "vds-1",
                "price": 5000,
                "status": "prolong_wait",
                "autoprolong": False,
                "paymentTerm": "month",
                "expiresAt": _iso(NOW - timedelta(days=1)),
            }
        ],
        "transactions": [],
    }
    assert predict_churn_score(customer, _config({"has_prolong_wait": 1000.0}), now=NOW) == 100
    assert predict_churn_score(customer, _config({"has_prolong_wait": -1000.0}), now=NOW) == 0


def test_invalid_config_rejected() -> None:
    """Невалидные параметры конфига отклоняются."""
    with pytest.raises(ValueError):
        ModelConfig(weights=WEIGHTS, expires_soon_days=0)
    with pytest.raises(ValueError):
        ModelConfig(weights={"has_prolong_wait": True})  # bool — не число
    with pytest.raises(ValueError):
        ModelConfig(weights={"has_prolong_wait": float("nan")})
    with pytest.raises(ValueError):
        ModelConfig(weights={"has_prolong_wait": float("inf")})
    with pytest.raises(ValueError):
        ModelConfig(weights={"has_prolong_wait": "3.0"})  # type: ignore[dict-item]
    with pytest.raises(ValueError):
        ModelConfig(weights={1: 3.0})  # type: ignore[dict-item]
    with pytest.raises(ValueError):
        ModelConfig(weights=WEIGHTS, bias=float("nan"))
