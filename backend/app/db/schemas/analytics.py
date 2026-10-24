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


class ChurnTrendBucket(CamelModel):
    """Одна неделя графика оттока: услуги с истечением в этот период"""

    period_start: UtcDateTime
    period_end: UtcDateTime
    # Период уже прошёл (факт по реальному текущему статусу услуг) или
    # ещё впереди (прогноз по уже посчитанному риску аккаунта-владельца)
    is_forecast: bool
    expired_services: int
    churned_services: int


class ChurnTrendOut(CamelModel):
    """График оттока по неделям (GET /analytics/churn-trend)"""

    buckets: list[ChurnTrendBucket]
    # Активные сейчас услуги, чей аккаунт-владелец в зоне high/medium риска
    at_risk_services: int
    generated_at: UtcDateTime
