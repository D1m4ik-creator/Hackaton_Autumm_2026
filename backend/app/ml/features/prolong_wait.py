"""prolong_wait — сильнейший сигнал оттока: услуга уже не оплачена и ждёт
удаления (через 5 дней, по данным кейса). Если при этом доступных средств не
хватает даже на эту одну услугу — усиливающий модификатор."""

from .base import CustomerContext, Feature


def _has_prolong_wait(ctx: CustomerContext) -> float:
    return 1.0 if ctx.prolong_wait_services else 0.0


def _prolong_wait_without_funds(ctx: CustomerContext) -> float:
    return 1.0 if ctx.prolong_wait_services and ctx.available_funds < ctx.prolong_wait_cost else 0.0


HAS_PROLONG_WAIT = Feature(
    code="has_prolong_wait",
    default_weight=3.0,
    reason_text="Есть услуга в статусе «Ожидает оплаты»",
    compute=_has_prolong_wait,
)

PROLONG_WAIT_WITHOUT_FUNDS = Feature(
    code="prolong_wait_without_funds",
    default_weight=2.0,
    reason_text="Ожидает оплаты, а денег на счёте не хватает",
    compute=_prolong_wait_without_funds,
)
