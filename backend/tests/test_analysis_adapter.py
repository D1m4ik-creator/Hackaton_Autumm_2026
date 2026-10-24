"""Тесты адаптера модели оттока (``app.analysis.churn``).

Чистые тесты без БД: входные данные берутся из реального снимка
``origin_data/data.json`` и из небольших синтетических ``SourceData``.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.analysis import analyze, default_settings, validate_settings
from app.analysis.types import (
    AccountData,
    ServiceData,
    SourceData,
    TransactionData,
)
from app.crud.recalc import check_result

AS_OF = datetime(2026, 10, 19, 15, 0, 0, tzinfo=timezone.utc)
DATA_PATH = Path(__file__).resolve().parents[2] / "origin_data" / "data.json"


def _dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _load_source() -> SourceData:
    """Строит SourceData из origin_data/data.json (camelCase -> snake_case)."""
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    accounts = [
        AccountData(
            id=a["id"],
            email=a["email"],
            balance=a["balance"],
            withdraw_balance=a["withdrawBalance"],
            total_replenished=a["totalReplenished"],
            bonus_balance=a["bonusBalance"],
            bonus_state=a["bonusState"],
        )
        for a in raw["accounts"]
    ]
    services = [
        ServiceData(
            id=s["id"],
            name=s["name"],
            owner_id=s["ownerId"],
            payment_term=s["paymentTerm"],
            auto_prolong=s["autoProlong"],
            created_at=_dt(s["createdAt"]),
            expires_at=_dt(s["expiresAt"]),
            status=s["status"],
            price=s["price"],
        )
        for s in raw["services"]
    ]
    transactions = [
        TransactionData(
            id=t["id"],
            amount=t["amount"],
            status=t["status"],
            performed_at=_dt(t["performedAt"]),
            created_at=_dt(t["createdAt"]),
            type=t["type"],
            service_id=t["serviceId"],
        )
        for t in raw["transactions"]
    ]
    return SourceData(accounts=accounts, services=services, transactions=transactions)


def _service(
    *,
    sid: int,
    owner: int,
    status: str,
    price: int,
    auto_prolong: bool,
    payment_term: str = "month",
    expires_at: datetime | None = None,
) -> ServiceData:
    expires_at = expires_at or (AS_OF + timedelta(days=3))
    return ServiceData(
        id=sid,
        name=f"svc-{sid}",
        owner_id=owner,
        payment_term=payment_term,
        auto_prolong=auto_prolong,
        created_at=AS_OF - timedelta(days=30),
        expires_at=expires_at,
        status=status,
        price=price,
    )


def _account(
    *, aid: int, balance: int = 0, bonus_balance: int = 0, bonus_state: str = "locked"
) -> AccountData:
    return AccountData(
        id=aid,
        email=f"user-{aid}@example.test",
        balance=balance,
        withdraw_balance=0,
        total_replenished=0,
        bonus_balance=bonus_balance,
        bonus_state=bonus_state,
    )


def _by_account(result) -> dict[int, object]:
    return {c.account_id: c for c in result.customers}


def test_real_data_passes_contract() -> None:
    """analyze на реальных данных проходит проверку контракта check_result."""
    source = _load_source()
    result = analyze(source, default_settings(), AS_OF)

    account_ids = {a.id for a in source.accounts}
    # Не бросает AnalysisContractError и возвращает всех клиентов.
    checked = check_result(result, account_ids)
    assert {c.account_id for c in checked} == account_ids
    assert isinstance(result.loss_explanation, str) and result.loss_explanation


def test_prolong_wait_scores_higher_than_deleted() -> None:
    """Клиент 5 (prolong_wait) рискованнее клиента 3 (deleted)."""
    source = _load_source()
    by_id = _by_account(analyze(source, default_settings(), AS_OF))

    assert by_id[5].score is not None
    assert by_id[3].score is not None
    assert by_id[5].score > by_id[3].score


def test_autoprolong_field_is_used() -> None:
    """Поле autoProlong реально учитывается: включённое -> меньший off_ratio."""
    account = _account(aid=1, balance=1_000_000)
    far = AS_OF + timedelta(days=200)
    source_on = SourceData(
        accounts=[account],
        services=[
            _service(sid=1, owner=1, status="active", price=5000, auto_prolong=True, expires_at=far),
            _service(sid=2, owner=1, status="active", price=5000, auto_prolong=True, expires_at=far),
        ],
        transactions=[],
    )
    source_off = SourceData(
        accounts=[account],
        services=[
            _service(sid=1, owner=1, status="active", price=5000, auto_prolong=False, expires_at=far),
            _service(sid=2, owner=1, status="active", price=5000, auto_prolong=False, expires_at=far),
        ],
        transactions=[],
    )
    on = _by_account(analyze(source_on, default_settings(), AS_OF))[1]
    off = _by_account(analyze(source_off, default_settings(), AS_OF))[1]

    assert on.details["features"]["autoprolong_off_ratio"] == 0.0
    assert off.details["features"]["autoprolong_off_ratio"] == 1.0
    assert off.score >= on.score


def test_bonus_state_affects_available_funds() -> None:
    """bonusState locked/unlocked меняет доступные средства -> balance_deficit."""
    service = _service(sid=1, owner=1, status="active", price=5000, auto_prolong=True)
    unlocked = SourceData(
        accounts=[_account(aid=1, balance=0, bonus_balance=6000, bonus_state="unlocked")],
        services=[service],
        transactions=[],
    )
    locked = SourceData(
        accounts=[_account(aid=1, balance=0, bonus_balance=6000, bonus_state="locked")],
        services=[service],
        transactions=[],
    )
    unlocked_c = _by_account(analyze(unlocked, default_settings(), AS_OF))[1]
    locked_c = _by_account(analyze(locked, default_settings(), AS_OF))[1]

    assert unlocked_c.details["features"]["balance_deficit"] == 0.0
    assert locked_c.details["features"]["balance_deficit"] == 1.0


def test_validate_settings_rejects_bad_values() -> None:
    """validate_settings отвергает недопустимые значения с ValueError."""
    base = default_settings()
    with pytest.raises(ValueError):
        validate_settings({**base, "thresholds": {"high": 30, "medium": 50}})
    with pytest.raises(ValueError):
        validate_settings({**base, "expiresSoonDays": 0})
    with pytest.raises(ValueError):
        validate_settings({**base, "horizonDays": 100000})
    with pytest.raises(ValueError):
        validate_settings({**base, "weights": {"has_prolong_wait": True}})
    with pytest.raises(ValueError):
        validate_settings({**base, "bias": float("inf")})
    with pytest.raises(ValueError):
        validate_settings({**base, "asOf": "не дата"})


def test_validate_settings_accepts_new_weight_and_keeps_unknown_keys() -> None:
    """Новый вес допускается (расширяемость), неизвестные ключи сохраняются."""
    data = {**default_settings(), "customKey": 42}
    data["weights"] = {**data["weights"], "my_new_feature": 1.7}
    normalized = validate_settings(data)

    assert normalized["weights"]["my_new_feature"] == 1.7
    assert normalized["customKey"] == 42


def test_new_weight_without_feature_gives_zero_contribution() -> None:
    """Вес без реализации в extract_features не ломает анализ (нулевой вклад)."""
    source = _load_source()
    settings = default_settings()
    settings["weights"] = {**settings["weights"], "unimplemented_feature": 5.0}
    result = analyze(source, validate_settings(settings), AS_OF)
    check_result(result, {a.id for a in source.accounts})


def test_level_thresholds_change_level() -> None:
    """Пороги уровней меняют level при той же вероятности."""
    source = _load_source()
    strict = validate_settings({**default_settings(), "thresholds": {"high": 99, "medium": 90}})
    lax = validate_settings({**default_settings(), "thresholds": {"high": 10, "medium": 5}})

    strict_c = _by_account(analyze(source, strict, AS_OF))[5]
    lax_c = _by_account(analyze(source, lax, AS_OF))[5]

    assert strict_c.score == lax_c.score
    # При жёстких порогах тот же клиент ниже по уровню, чем при мягких.
    order = {"no_data": -1, "low": 0, "medium": 1, "high": 2}
    assert order[strict_c.level] < order[lax_c.level]


def test_no_data_customer_has_zero_loss() -> None:
    """Клиент без услуг и транзакций -> no_data, score None, потери 0."""
    source = SourceData(
        accounts=[_account(aid=1, balance=1000)],
        services=[],
        transactions=[],
    )
    customer = _by_account(analyze(source, default_settings(), AS_OF))[1]

    assert customer.level == "no_data"
    assert customer.score is None
    assert customer.expected_loss_cents == 0
    assert customer.reasons[0].code == "no_data"


def test_live_customer_with_risk_has_positive_loss() -> None:
    """Клиент с живыми услугами и ненулевой вероятностью -> потери > 0."""
    source = _load_source()
    by_id = _by_account(analyze(source, default_settings(), AS_OF))
    customer = by_id[5]  # prolong_wait, высокий риск

    assert customer.details["probability"] > 0
    assert customer.expected_loss_cents > 0


def test_details_are_json_serializable() -> None:
    """details каждого клиента сериализуется в JSON без NaN."""
    source = _load_source()
    result = analyze(source, default_settings(), AS_OF)
    for customer in result.customers:
        json.dumps(customer.details, allow_nan=False)


def test_validate_settings_accepts_custom_feature() -> None:
    """Пользовательская метрика с валидной формулой проходит нормализацию."""
    data = {
        **default_settings(),
        "customFeatures": {"big_spender": {"label": "Крупный плательщик", "formula": "total_replenished > 300000"}},
    }
    normalized = validate_settings(data)
    assert normalized["customFeatures"]["big_spender"] == {
        "label": "Крупный плательщик",
        "formula": "total_replenished > 300000",
    }


@pytest.mark.parametrize(
    "custom_features",
    [
        {"1bad": {"label": "x", "formula": "1"}},  # код не с буквы
        {"ab": {"label": "x", "formula": "1"}},  # слишком короткий код
        {"has_prolong_wait": {"label": "x", "formula": "1"}},  # зарезервирован встроенным признаком
        {"ok_code": {"label": "", "formula": "1"}},  # пустой label
        {"ok_code": {"label": "x", "formula": ""}},  # пустая формула
        {"ok_code": {"label": "x", "formula": "__import__('os')"}},  # опасная формула
        {"ok_code": "not-a-dict"},  # значение не объект
        "not-a-dict",  # вся секция не объект
    ],
)
def test_validate_settings_rejects_bad_custom_feature(custom_features) -> None:
    with pytest.raises(ValueError):
        validate_settings({**default_settings(), "customFeatures": custom_features})


def test_analyze_applies_custom_feature_weight_and_reason() -> None:
    """Кастомная метрика с ненулевым весом реально влияет на score и попадает в reasons."""
    source = _load_source()
    base_settings = default_settings()
    zero_weight = validate_settings({
        **base_settings,
        "customFeatures": {"big_spender": {"label": "Крупный плательщик", "formula": "total_replenished > 1"}},
        "weights": {**base_settings["weights"], "big_spender": 0.0},
    })
    high_weight = validate_settings({
        **base_settings,
        "customFeatures": {"big_spender": {"label": "Крупный плательщик", "formula": "total_replenished > 1"}},
        "weights": {**base_settings["weights"], "big_spender": 10.0},
    })

    zero_c = _by_account(analyze(source, zero_weight, AS_OF))[5]
    high_c = _by_account(analyze(source, high_weight, AS_OF))[5]

    assert zero_c.score is not None and high_c.score is not None
    assert high_c.score > zero_c.score
    assert "big_spender" in high_c.details["features"]
    assert any(r.code == "big_spender" and r.text == "Крупный плательщик" for r in high_c.reasons)


def test_analyze_without_custom_features_is_unaffected() -> None:
    """Без customFeatures поведение analyze не меняется (обратная совместимость)."""
    source = _load_source()
    with_key = {**default_settings(), "customFeatures": {}}
    without_key = default_settings()
    with_c = _by_account(analyze(source, with_key, AS_OF))
    without_c = _by_account(analyze(source, without_key, AS_OF))
    for account_id in with_c:
        assert with_c[account_id].score == without_c[account_id].score
