from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.risk_summary import RiskSummaryDAO
from app.db.models.risk_result import RiskResult
from app.db.models.service import Service
from app.db.schemas.analytics import ChurnTrendBucket, ChurnTrendOut, SummaryOut
from app.db.schemas.common import LEVELS, level_bucket

# Статусы, которые считаем «продлена» — всё остальное (deleted/blocked/suspended)
# к прошедшему периоду означает отток. Совпадает с ACTIVE_STATUSES в churn_model.py.
RENEWED_STATUSES = frozenset({"active", "prolong_wait"})
AT_RISK_LEVELS = frozenset({"high", "medium"})


async def get_summary(session: AsyncSession) -> SummaryOut:
    """Сводка по всем клиентам из единственной строки risk_summary"""
    summary = await RiskSummaryDAO.get(session)
    by_level = (summary.by_level if summary else None) or {}
    return SummaryOut(
        customers_total=summary.customers_total if summary else 0,
        by_level={key: level_bucket(by_level, key) for key in LEVELS},
        expected_loss_cents=summary.expected_loss_cents if summary else 0,
        loss_explanation=summary.loss_explanation if summary else "",
        as_of=summary.as_of if summary else None,
        recalculated_at=summary.recalculated_at if summary else None,
        version=summary.version if summary else 0,
    )


def _week_start(value: datetime) -> datetime:
    """Понедельник 00:00 UTC недели, в которую попадает value"""
    value = value.astimezone(timezone.utc)
    monday = value - timedelta(days=value.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


async def get_churn_trend(session: AsyncSession, weeks_back: int = 8, weeks_forward: int = 8) -> ChurnTrendOut:
    """
    График оттока по неделям: факт (услуги с истёкшим сроком, статус которых к
    текущему моменту отличен от active/prolong_wait — не продлена) и прогноз
    (ещё активные услуги с истечением в будущем периоде, помечаем как вероятный
    отток при auto_prolong=false либо если аккаунт-владелец уже в зоне high
    риска по посчитанной модели — backend/app/predictt_model/churn_model.py).

    В снимке данных нет метки времени удаления услуги (services.deleted_at),
    поэтому и факт, и прогноз группируются по expires_at — это ближайшее
    честное приближение без миграции схемы: период истечения совпадает с
    моментом, когда решается «продлевать/нет», что по сути и есть отток.
    """
    now = datetime.now(timezone.utc)
    current_week = _week_start(now)
    range_start = current_week - timedelta(weeks=weeks_back)
    range_end = current_week + timedelta(weeks=weeks_forward + 1)

    services = (
        await session.execute(
            select(Service.owner_id, Service.expires_at, Service.status, Service.auto_prolong)
            .where(Service.expires_at >= range_start, Service.expires_at < range_end)
        )
    ).all()

    risk_levels = dict((await session.execute(select(RiskResult.account_id, RiskResult.level))).all())

    buckets: dict[datetime, dict[str, int]] = defaultdict(lambda: {"expired": 0, "churned": 0})
    for owner_id, expires_at, status, auto_prolong in services:
        bucket_start = _week_start(expires_at)
        bucket = buckets[bucket_start]
        bucket["expired"] += 1

        if bucket_start < current_week:
            # Факт: период уже прошёл, смотрим на реальный текущий статус
            if status not in RENEWED_STATUSES:
                bucket["churned"] += 1
        elif status not in RENEWED_STATUSES:
            # Досрочно ушла ещё до наступления «будущего» периода — это уже факт,
            # не прогноз, даже если период попадает в будущее окно
            bucket["churned"] += 1
        else:
            # Прогноз: ещё активна, решение о продлении впереди
            predicted_churn = (not auto_prolong) or (risk_levels.get(owner_id) == "high")
            if predicted_churn:
                bucket["churned"] += 1

    result_buckets: list[ChurnTrendBucket] = []
    cursor = range_start
    while cursor < range_end - timedelta(days=1):
        data = buckets.get(cursor, {"expired": 0, "churned": 0})
        result_buckets.append(
            ChurnTrendBucket(
                period_start=cursor,
                period_end=cursor + timedelta(days=7),
                is_forecast=cursor >= current_week,
                expired_services=data["expired"],
                churned_services=data["churned"],
            )
        )
        cursor += timedelta(weeks=1)

    at_risk_services = (
        await session.execute(
            select(Service.id)
            .where(Service.status.in_(RENEWED_STATUSES))
            .where(Service.owner_id.in_(select(RiskResult.account_id).where(RiskResult.level.in_(AT_RISK_LEVELS))))
        )
    ).all()

    return ChurnTrendOut(
        buckets=result_buckets,
        at_risk_services=len(at_risk_services),
        generated_at=now,
    )
