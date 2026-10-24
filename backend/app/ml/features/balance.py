"""balance_deficit / sufficient_funds — доступные средства против стоимости
ближайших продлений (уже ждущих оплаты услуг + активных, истекающих в окне
expires_soon_days). Два взаимоисключающих взгляда на один и тот же расчёт:
первый — рисковый сигнал, второй — защитный (отрицательный вес по умолчанию)."""

from .base import CustomerContext, Feature


def _balance_deficit(ctx: CustomerContext) -> float:
    return 1.0 if ctx.upcoming_cost > 0 and ctx.available_funds < ctx.upcoming_cost else 0.0


def _sufficient_funds(ctx: CustomerContext) -> float:
    return 1.0 if ctx.upcoming_cost > 0 and ctx.available_funds >= ctx.upcoming_cost else 0.0


BALANCE_DEFICIT = Feature(
    code="balance_deficit",
    default_weight=1.5,
    reason_text="Баланса не хватает на ближайшие продления",
    compute=_balance_deficit,
)

SUFFICIENT_FUNDS = Feature(
    code="sufficient_funds",
    default_weight=-0.8,
    reason_text="Средств хватает на ближайшие продления",
    compute=_sufficient_funds,
)
