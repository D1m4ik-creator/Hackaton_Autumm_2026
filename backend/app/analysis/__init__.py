"""Единственная точка входа модуля анализа.

Инфраструктура импортирует отсюда ``default_settings``, ``validate_settings`` и
``analyze``. Чтобы подключить реальную модель, ML-команда реализует эти три
функции в своих модулях пакета и меняет импорт ниже (сейчас — из ``stub``).
"""

from app.analysis.stub import analyze, default_settings, validate_settings
from app.analysis.types import (
    AccountData,
    AnalysisResult,
    CustomerRisk,
    Level,
    Reason,
    ServiceData,
    SourceData,
    TransactionData,
)

__all__ = [
    "analyze",
    "default_settings",
    "validate_settings",
    "AccountData",
    "AnalysisResult",
    "CustomerRisk",
    "Level",
    "Reason",
    "ServiceData",
    "SourceData",
    "TransactionData",
]
