from app.db.schemas.common import CamelModel, UtcDateTime


class LevelBucket(CamelModel):
    """Агрегат по одному уровню риска: число клиентов и сумма ожидаемых потерь"""

    customers: int
    expected_loss_cents: int


class ByLevel(CamelModel):
    """Агрегаты по всем четырём уровням риска"""

    high: LevelBucket
    medium: LevelBucket
    low: LevelBucket
    no_data: LevelBucket


class SummaryOut(CamelModel):
    """Сводка по всем клиентам (GET /analytics/summary)"""

    customers_total: int
    by_level: ByLevel
    expected_loss_cents: int
    loss_explanation: str
    as_of: UtcDateTime | None
    recalculated_at: UtcDateTime | None
    version: int
