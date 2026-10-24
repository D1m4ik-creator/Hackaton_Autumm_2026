"""Юнит-тесты для churn_model (pytest)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.ml.churn_model import (
    ModelConfig,
    extract_features,
    predict_churn,
    predict_churn_with_explanation,
)

NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def test_prolong_wait_without_funds_predicts_churn() -> None:
    """Клиент с услугой в prolong_wait и пустым балансом -> уйдёт."""
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
    decision, probability, explanation = predict_churn_with_explanation(customer, now=NOW)

    assert decision is True
    assert probability >= 0.5
    assert explanation["insufficient_data"] is False
    # Оба ключевых сигнала должны дать положительный вклад.
    assert explanation["contributions"]["has_prolong_wait"] > 0
    assert explanation["contributions"]["prolong_wait_without_funds"] > 0
    # В predict_churn тот же клиент тоже уходит.
    assert predict_churn(customer, now=NOW) is True


def test_loyal_customer_with_autoprolong_and_money_stays() -> None:
    """Автопродление + большой баланс -> останется."""
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
    decision, probability, explanation = predict_churn_with_explanation(customer, now=NOW)

    assert decision is False
    assert probability < 0.5
    # Защитные признаки сработали.
    assert explanation["features"]["full_autoprolong_coverage"] == 1.0
    assert explanation["features"]["sufficient_funds"] == 1.0


def test_empty_customer_does_not_raise_and_flags_insufficient_data() -> None:
    """Пустые данные -> без исключений, False, флаг insufficient_data."""
    for customer in ({}, {"services": [], "transactions": []}):
        decision, probability, explanation = predict_churn_with_explanation(customer, now=NOW)
        assert decision is False
        assert probability == 0.0
        assert explanation["insufficient_data"] is True
        assert predict_churn(customer, now=NOW) is False


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
    decision, _, explanation = predict_churn_with_explanation(customer, now=NOW)
    assert decision is False
    assert explanation["insufficient_data"] is False
    assert explanation["features"]["failed_payment_ratio"] == 0.0


def test_failed_payments_and_no_autoprolong_push_towards_churn() -> None:
    """Много неуспешных платежей + ручные продления -> риск растёт."""
    customer = {
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
    decision, probability, explanation = predict_churn_with_explanation(customer, now=NOW)

    assert decision is True
    assert explanation["features"]["failed_payment_ratio"] == 2 / 3
    assert explanation["features"]["expires_soon_no_autoprolong"] == 1.0
    assert explanation["features"]["balance_deficit"] == 1.0
    assert probability >= 0.5


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
    decision, _, explanation = predict_churn_with_explanation(customer, now=NOW)

    assert decision is False
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
    with_bonus = extract_features({**base, "bonusState": True}, ModelConfig(), now=NOW)
    without_bonus = extract_features({**base, "bonusState": False}, ModelConfig(), now=NOW)

    assert with_bonus["balance_deficit"] == 0.0
    assert without_bonus["balance_deficit"] == 1.0


def test_custom_threshold_and_weights_are_editable() -> None:
    """Порог и веса настраиваются через конфиг без изменения кода."""
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
    # Очень строгий порог: даже prolong_wait не дотягивает.
    strict = ModelConfig(threshold=0.999)
    assert predict_churn(customer, config=strict, now=NOW) is False

    # Мягкий порог: тот же клиент — отток.
    soft = ModelConfig(threshold=0.1)
    assert predict_churn(customer, config=soft, now=NOW) is True

    # Новый вес можно просто добавить в словарь.
    config = ModelConfig(weights={"has_prolong_wait": 0.0}, threshold=0.5)
    assert predict_churn(customer, config=config, now=NOW) is False


def test_invalid_config_rejected() -> None:
    """Невалидные параметры конфига отклоняются."""
    import pytest

    with pytest.raises(ValueError):
        ModelConfig(threshold=1.5)
    with pytest.raises(ValueError):
        ModelConfig(expires_soon_days=0)
