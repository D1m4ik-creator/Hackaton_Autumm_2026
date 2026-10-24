"""Единственная точка входа модуля анализа.

Инфраструктура импортирует отсюда ``default_settings``, ``validate_settings`` и
``analyze``. Подключена логистическая модель оттока через адаптер
``app/analysis/churn.py`` (модель — ``app/ml/churn_model.py``).
"""

from app.analysis.churn import analyze, default_settings, validate_settings
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
