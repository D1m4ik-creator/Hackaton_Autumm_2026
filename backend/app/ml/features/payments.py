"""failed_payment_ratio — доля неуспешных платежей: прямая история проблем
с оплатой. amount транзакций намеренно не используется (не связан с price
услуг, см. backend/docs/PLAN_churn_analyzer.md), только факт неудачи."""

from .base import CustomerContext, Feature


def _failed_payment_ratio(ctx: CustomerContext) -> float:
    total_tx = len(ctx.transactions)
    if not total_tx:
        return 0.0
    failed = sum(1 for t in ctx.transactions if t.get("status") == "not_performed")
    return failed / total_tx


FAILED_PAYMENT_RATIO = Feature(
    code="failed_payment_ratio",
    default_weight=2.0,
    reason_text="Много неуспешных платежей",
    compute=_failed_payment_ratio,
)
