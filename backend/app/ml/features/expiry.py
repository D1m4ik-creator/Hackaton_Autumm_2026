"""expires_soon_no_autoprolong — среди активных услуг, истекающих в
ближайшие expires_soon_days дней, есть хотя бы одна без автопродления:
точка принятия решения уже близко, а автоматики нет."""

from .base import CustomerContext, Feature


def _expires_soon_no_autoprolong(ctx: CustomerContext) -> float:
    return 1.0 if any(not s.get("autoprolong") for s in ctx.expiring_soon) else 0.0


EXPIRES_SOON_NO_AUTOPROLONG = Feature(
    code="expires_soon_no_autoprolong",
    default_weight=1.2,
    reason_text="Услуга скоро истекает, автопродление выключено",
    compute=_expires_soon_no_autoprolong,
)
