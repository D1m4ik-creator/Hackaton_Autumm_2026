"""autoprolong_off_ratio / full_autoprolong_coverage — доля активных услуг
без автопродления (риск) и обратный случай: автопродление включено
абсолютно везде (защитный сигнал — клиент настроил и забыл)."""

from .base import CustomerContext, Feature


def _autoprolong_off_ratio(ctx: CustomerContext) -> float:
    if not ctx.active_services:
        return 0.0
    return sum(1 for s in ctx.active_services if not s.get("autoprolong")) / len(ctx.active_services)


def _full_autoprolong_coverage(ctx: CustomerContext) -> float:
    return 1.0 if ctx.active_services and all(s.get("autoprolong") for s in ctx.active_services) else 0.0


AUTOPROLONG_OFF_RATIO = Feature(
    code="autoprolong_off_ratio",
    default_weight=1.5,
    reason_text="У активных услуг выключено автопродление",
    compute=_autoprolong_off_ratio,
)

FULL_AUTOPROLONG_COVERAGE = Feature(
    code="full_autoprolong_coverage",
    default_weight=-1.0,
    reason_text="Всё продлевается автоматически",
    compute=_full_autoprolong_coverage,
)
