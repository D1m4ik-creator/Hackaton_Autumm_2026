"""Пользовательские метрики по формуле — вводит админ/суперадмин через панель
настроек (не разработчик, не новый файл в реестре).

Формула считается через ``simpleeval`` — безопасный вычислитель выражений,
который разбирает строку через ``ast`` и выполняет только разрешённые
операции (арифметика, сравнения, явный белый список имён/функций). Прямое
``eval()``/``exec()`` пользовательской строки на боевых данных клиентов было
бы удалённым выполнением кода — поэтому не используется.
"""

from __future__ import annotations

from simpleeval import simple_eval

from .base import CONTEXT_VARIABLE_NAMES, CustomerContext, Feature, context_variables

FORMULA_FUNCTIONS = {"min": min, "max": max, "abs": abs}


def validate_formula(formula: str) -> None:
    """Пробный расчёт на нулевых значениях — ловит синтаксис и запрещённые
    операции на этапе сохранения настроек, а не во время скоринга клиентов."""
    dummy_names = dict.fromkeys(CONTEXT_VARIABLE_NAMES, 0.0)
    try:
        simple_eval(formula, names=dummy_names, functions=FORMULA_FUNCTIONS)
    except Exception as exc:
        raise ValueError(f"Некорректная формула: {exc}") from exc


def make_custom_feature(code: str, label: str, formula: str) -> Feature:
    def _compute(ctx: CustomerContext) -> float:
        try:
            result = simple_eval(formula, names=context_variables(ctx), functions=FORMULA_FUNCTIONS)
        except Exception:
            # Ошибка в рантайме (например деление на ноль в самодельной
            # формуле) не должна ронять пересчёт всех клиентов.
            return 0.0
        if isinstance(result, bool):
            return 1.0 if result else 0.0
        if isinstance(result, (int, float)):
            return max(0.0, min(1.0, float(result)))
        return 0.0

    return Feature(code=code, default_weight=0.0, reason_text=label, compute=_compute)
