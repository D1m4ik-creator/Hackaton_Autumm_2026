from datetime import datetime, timezone
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Базовая схема API: в Python snake_case, в JSON camelCase"""

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
        from_attributes=True,
    )


def _ensure_utc(value: datetime) -> datetime:
    """Наивную дату считаем UTC (по §4.1), дату с зоной оставляем как есть"""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


# Дата, у которой отсутствие зоны трактуется как UTC
UtcDateTime = Annotated[datetime, AfterValidator(_ensure_utc)]


# Все уровни риска в порядке вывода — в сводке всегда присутствуют все четыре ключа
LEVELS: tuple[str, ...] = ("high", "medium", "low", "no_data")


def level_bucket(by_level: dict, level: str) -> dict:
    """Агрегат одного уровня из risk_summary.by_level; отсутствующий уровень = нули"""
    data = by_level.get(level) or {}
    return {
        "customers": data.get("customers", 0),
        "expectedLossCents": data.get("expectedLossCents", 0),
    }
