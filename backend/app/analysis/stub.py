"""Заглушка модуля анализа (§5).

Пока ML-команда не подключила модель, каждому клиенту возвращается уровень
``no_data`` без денежной оценки. Формул модели здесь нет и быть не должно.
"""

from datetime import datetime

from app.analysis.types import AnalysisResult, CustomerRisk, Reason, SourceData


def default_settings() -> dict:
    """Настройки по умолчанию (JSON-сериализуемые)"""
    return {"asOf": None}


def validate_settings(data: dict) -> dict:
    """Нормализует настройки; при ошибке — ValueError с понятным текстом"""
    if not isinstance(data, dict):
        raise ValueError("Настройки должны быть объектом JSON")
    as_of = data.get("asOf")
    if as_of is not None:
        if not isinstance(as_of, str):
            raise ValueError("asOf должен быть строкой ISO-8601 или null")
        try:
            datetime.fromisoformat(as_of.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"asOf не является датой ISO-8601: {as_of!r}") from exc
    return dict(data)


def analyze(source: SourceData, settings: dict, as_of: datetime) -> AnalysisResult:
    """Заглушка: все клиенты получают уровень no_data без денежной оценки"""
    customers = [
        CustomerRisk(
            account_id=account.id,
            score=None,
            level="no_data",
            reasons=[Reason("model_not_connected", "Модель анализа ещё не подключена")],
            expected_loss_cents=0,
            details={},
        )
        for account in source.accounts
    ]
    return AnalysisResult(
        customers=customers,
        loss_explanation="Модель анализа ещё не подключена, денежная оценка не считается",
    )
