from typing import Annotated, Literal

from pydantic import AliasChoices, Field

from app.db.schemas.common import CamelModel, UtcDateTime

# Верхняя граница BIGINT — числа крупнее дают DataError в asyncpg (хотим 422, а не 500)
_BIGINT_MAX = 9_223_372_036_854_775_807
BigIntId = Annotated[int, Field(ge=1, le=_BIGINT_MAX)]
BigIntValue = Annotated[int, Field(ge=0, le=_BIGINT_MAX)]


class SnapshotAccountIn(CamelModel):
    """Аккаунт во входном снимке (форма data.json, лишние поля игнорируются)"""

    id: BigIntId
    email: str = Field(min_length=1)
    balance: BigIntValue
    withdraw_balance: BigIntValue
    total_replenished: BigIntValue
    bonus_balance: BigIntValue
    bonus_state: Literal["locked", "unlocked"]


class SnapshotServiceIn(CamelModel):
    """Услуга во входном снимке"""

    id: BigIntId
    name: str
    owner_id: BigIntId
    payment_term: Literal["hour", "week", "month", "quarter_year", "half_year", "year"]
    # В данных встречается и autoProlong, и autoprolong
    auto_prolong: bool = Field(validation_alias=AliasChoices("autoProlong", "autoprolong"))
    created_at: UtcDateTime
    expires_at: UtcDateTime
    status: Literal["active", "blocked", "deleted", "suspended", "prolong_wait"]
    price: BigIntValue


class SnapshotTransactionIn(CamelModel):
    """Транзакция во входном снимке"""

    id: BigIntId
    amount: int = Field(ge=0, le=1000)
    status: Literal["performed", "not_performed"]
    performed_at: UtcDateTime | None = None
    created_at: UtcDateTime
    type: Literal["prolong", "order"]
    service_id: BigIntId


class SnapshotIn(CamelModel):
    """Полный входной снимок исходных данных"""

    accounts: list[SnapshotAccountIn]
    services: list[SnapshotServiceIn]
    transactions: list[SnapshotTransactionIn]


class SnapshotLoadResult(CamelModel):
    """Результат загрузки снимка: что загружено и новая версия сводки"""

    accounts: int
    services: int
    transactions: int
    version: int
    recalculated_at: UtcDateTime
