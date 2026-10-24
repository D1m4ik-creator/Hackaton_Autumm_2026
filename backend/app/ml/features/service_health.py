"""suspended_ratio / deleted_blocked_ratio — доля услуг, уже приостановленных
(обычно за неуплату) или удалённых/заблокированных (клиент уже уходил раньше —
исторический сигнал, не завязан на текущее окно времени)."""

from .base import CustomerContext, Feature


def _suspended_ratio(ctx: CustomerContext) -> float:
    total_services = len(ctx.services)
    return len(ctx.suspended_services) / total_services if total_services else 0.0


def _deleted_blocked_ratio(ctx: CustomerContext) -> float:
    total_services = len(ctx.services)
    return len(ctx.gone_services) / total_services if total_services else 0.0


SUSPENDED_RATIO = Feature(
    code="suspended_ratio",
    default_weight=1.0,
    reason_text="Часть услуг приостановлена",
    compute=_suspended_ratio,
)

DELETED_BLOCKED_RATIO = Feature(
    code="deleted_blocked_ratio",
    default_weight=1.0,
    reason_text="Раньше удалял или потерял услуги",
    compute=_deleted_blocked_ratio,
)
