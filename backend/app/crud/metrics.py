from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.risk_summary import RiskSummaryDAO
from app.db.schemas.common import LEVELS, level_bucket


async def render_metrics(session: AsyncSession) -> str:
    """Текст метрик Prometheus из той же строки risk_summary, что и /analytics/summary"""
    summary = await RiskSummaryDAO.get(session)
    by_level = (summary.by_level if summary else None) or {}

    def customers(level: str) -> int:
        return level_bucket(by_level, level)["customers"]

    def loss(level: str) -> int:
        return level_bucket(by_level, level)["expectedLossCents"]

    total_loss = summary.expected_loss_cents if summary else 0
    version = summary.version if summary else 0
    recalculated_at = summary.recalculated_at if summary else None
    last_ts = int(recalculated_at.timestamp()) if recalculated_at else 0

    lines: list[str] = [
        "# HELP churn_customers Количество клиентов по уровню риска",
        "# TYPE churn_customers gauge",
        *[f'churn_customers{{level="{level}"}} {customers(level)}' for level in LEVELS],
        "# HELP churn_expected_loss_eurocents Ожидаемые потери, евроценты",
        "# TYPE churn_expected_loss_eurocents gauge",
        f"churn_expected_loss_eurocents {total_loss}",
        "# HELP churn_expected_loss_by_level_eurocents Ожидаемые потери по уровню риска, евроценты",
        "# TYPE churn_expected_loss_by_level_eurocents gauge",
        *[f'churn_expected_loss_by_level_eurocents{{level="{level}"}} {loss(level)}' for level in LEVELS],
        "# HELP churn_last_recalculation_timestamp_seconds Время последнего пересчёта, unixtime",
        "# TYPE churn_last_recalculation_timestamp_seconds gauge",
        f"churn_last_recalculation_timestamp_seconds {last_ts}",
        "# HELP churn_recalculations_total Число пересчётов",
        "# TYPE churn_recalculations_total counter",
        f"churn_recalculations_total {version}",
    ]
    return "\n".join(lines) + "\n"
