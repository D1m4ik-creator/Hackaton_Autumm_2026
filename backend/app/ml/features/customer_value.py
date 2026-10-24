"""customer_value — ценность клиента для компании (сумма пополнений), а не
поведенческий сигнал риска: сам по себе большой totalReplenished не означает
скорый уход. Поэтому вес по умолчанию 0 — признак виден и настраивается через
панель, но не влияет на score, пока администратор не задаст ему вес вручную.

Линейная нормализация в [0, 1] с насыщением на _SATURATION_CENTS: клиент с
пополнениями выше порога получает максимальное значение 1.0, остальные —
пропорционально. Порог — внутренняя константа признака (не параметр
ModelConfig): как и остальные признаки, этот не требует межклиентского
сравнения, только собственные данные клиента.
"""

from .base import CustomerContext, Feature

_SATURATION_CENTS = 200_000  # 2000 € пополнений — условный порог «крупный клиент»


def _customer_value(ctx: CustomerContext) -> float:
    total_replenished = float(ctx.customer.get("totalReplenished") or 0)
    if total_replenished <= 0:
        return 0.0
    return max(0.0, min(1.0, total_replenished / _SATURATION_CENTS))


CUSTOMER_VALUE = Feature(
    code="customer_value",
    default_weight=0.0,
    reason_text="Клиент приносит компании много денег (крупные пополнения)",
    compute=_customer_value,
)
