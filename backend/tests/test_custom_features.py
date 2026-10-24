"""Тесты безопасного вычислителя пользовательских метрик (app.ml.features.custom)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.ml.features.base import build_context
from app.ml.features.custom import make_custom_feature, validate_formula

AS_OF = datetime(2026, 10, 19, 15, 0, 0, tzinfo=timezone.utc)


def _customer(**overrides) -> dict:
    base = {
        "id": 1,
        "balance": 10000,
        "bonusBalance": 0,
        "bonusState": False,
        "totalReplenished": 0,
        "services": [],
        "transactions": [],
    }
    base.update(overrides)
    return base


@pytest.mark.parametrize(
    "formula",
    [
        "balance > 1000",
        "min(balance, total_replenished)",
        "max(balance, 0) / 100",
        "abs(balance - total_replenished)",
        "1 if balance > 0 else 0",
        "total_transactions == 0",
    ],
)
def test_validate_formula_accepts_safe_expressions(formula: str) -> None:
    validate_formula(formula)  # не бросает


@pytest.mark.parametrize(
    "formula",
    [
        "__import__('os').system('id')",
        "open('/etc/passwd')",
        "().__class__.__bases__",
        "balance.__class__",
        "getattr(balance, '__class__')",
        "import os",
        "1 +",
        "undefined_name + 1",
    ],
)
def test_validate_formula_rejects_malicious_or_broken_expressions(formula: str) -> None:
    with pytest.raises(ValueError):
        validate_formula(formula)


def test_make_custom_feature_computes_from_context() -> None:
    feature = make_custom_feature("big_spender", "Крупный плательщик", "total_replenished > 300000")
    ctx_rich = build_context(_customer(totalReplenished=500_000), expires_soon_days=7, now=AS_OF)
    ctx_poor = build_context(_customer(totalReplenished=100), expires_soon_days=7, now=AS_OF)

    assert feature.value(ctx_rich) == 1.0
    assert feature.value(ctx_poor) == 0.0
    assert feature.code == "big_spender"
    assert feature.reason_text == "Крупный плательщик"
    assert feature.default_weight == 0.0


def test_make_custom_feature_clamps_result_to_unit_range() -> None:
    feature = make_custom_feature("over", "over", "total_replenished / 100")
    ctx = build_context(_customer(totalReplenished=1_000_000), expires_soon_days=7, now=AS_OF)
    assert feature.value(ctx) == 1.0


def test_make_custom_feature_runtime_error_gives_zero_not_crash() -> None:
    feature = make_custom_feature("div", "div", "1 / (balance - balance)")
    ctx = build_context(_customer(balance=5000), expires_soon_days=7, now=AS_OF)
    assert feature.value(ctx) == 0.0
