"""Реестр признаков модели — единственное место, где собираются все Feature.

Чтобы добавить новый признак: создать ``Feature`` в своём файле (см. соседние
модули для примера — один признак или тесно связанная пара на файл) и
добавить его в ``FEATURE_REGISTRY`` ниже. Больше ничего менять не нужно:
``extract_features`` (app/ml/churn_model.py) и дефолтные веса/тексты причин
(app/analysis/churn.py) строятся из этого списка автоматически.
"""

from .autoprolong import AUTOPROLONG_OFF_RATIO, FULL_AUTOPROLONG_COVERAGE
from .balance import BALANCE_DEFICIT, SUFFICIENT_FUNDS
from .base import CustomerContext, Feature, build_context
from .customer_value import CUSTOMER_VALUE
from .expiry import EXPIRES_SOON_NO_AUTOPROLONG
from .payments import FAILED_PAYMENT_RATIO
from .prolong_wait import HAS_PROLONG_WAIT, PROLONG_WAIT_WITHOUT_FUNDS
from .service_health import DELETED_BLOCKED_RATIO, SUSPENDED_RATIO

FEATURE_REGISTRY: list[Feature] = [
    HAS_PROLONG_WAIT,
    PROLONG_WAIT_WITHOUT_FUNDS,
    FAILED_PAYMENT_RATIO,
    BALANCE_DEFICIT,
    SUFFICIENT_FUNDS,
    AUTOPROLONG_OFF_RATIO,
    FULL_AUTOPROLONG_COVERAGE,
    EXPIRES_SOON_NO_AUTOPROLONG,
    SUSPENDED_RATIO,
    DELETED_BLOCKED_RATIO,
    CUSTOMER_VALUE,
]

__all__ = ["CustomerContext", "Feature", "build_context", "FEATURE_REGISTRY"]
