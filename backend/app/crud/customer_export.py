import csv
import io
import json
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Literal

from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from sqlalchemy import Row
from sqlalchemy.ext.asyncio import AsyncSession

import app.dao.customer_query as customer_query

ExportFormat = Literal["csv", "xlsx", "json"]

MEDIA_TYPES: dict[str, str] = {
    "csv": "text/csv; charset=utf-8",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "json": "application/json",
}

LEVEL_LABELS = {"high": "Высокий", "medium": "Средний", "low": "Низкий", "no_data": "Нет данных"}

# Заголовки для людей (CSV/Excel): деньги в евро, уровень по-русски
HEADERS = [
    "ID",
    "Email",
    "Уровень риска",
    "Риск, %",
    "Ожидаемые потери, €",
    "Баланс, €",
    "К выводу, €",
    "Бонусы, €",
    "Бонусы разблокированы",
    "Всего пополнено, €",
    "Главная причина",
]

# Ячейка, начинающаяся с этих символов, в Excel станет формулой (CSV/formula injection)
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _safe_text(value: str) -> str:
    return f"'{value}" if value.startswith(_FORMULA_PREFIXES) else value


def _euro(cents: int) -> float:
    return round(cents / 100, 2)


def _table_row(row: Row) -> list:
    return [
        row.id,
        _safe_text(row.email),
        LEVEL_LABELS.get(row.level, row.level),
        row.score,
        _euro(row.expected_loss_cents),
        _euro(row.balance),
        _euro(row.withdraw_balance),
        _euro(row.bonus_balance),
        "да" if row.bonus_state == "unlocked" else "нет",
        _euro(row.total_replenished),
        _safe_text(row.reason_short),
    ]


def _json_row(row: Row) -> dict:
    """Те же ключи и единицы (центы), что в GET /customers, плюс поля счёта"""
    return {
        "id": row.id,
        "email": row.email,
        "level": row.level,
        "riskScore": row.score,
        "expectedLossCents": row.expected_loss_cents,
        "balance": row.balance,
        "withdrawBalance": row.withdraw_balance,
        "bonusBalance": row.bonus_balance,
        "bonusState": row.bonus_state,
        "totalReplenished": row.total_replenished,
        "reasonShort": row.reason_short,
    }


def _to_csv(rows: Sequence[Row]) -> bytes:
    buffer = io.StringIO()
    # «;» и BOM — чтобы Excel с русской локалью открыл файл двойным кликом без мастера импорта
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(HEADERS)
    writer.writerows(_table_row(row) for row in rows)
    return ("﻿" + buffer.getvalue()).encode("utf-8")


def _to_xlsx(rows: Sequence[Row]) -> bytes:
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("Клиенты")
    widths = [12, 32, 14, 9, 18, 12, 12, 12, 12, 16, 48]
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    sheet.freeze_panes = "A2"
    sheet.append(HEADERS)
    for row in rows:
        sheet.append(_table_row(row))
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _to_json(rows: Sequence[Row]) -> bytes:
    payload = {"exportedAt": datetime.now(timezone.utc).isoformat(), "items": [_json_row(row) for row in rows]}
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


_WRITERS = {"csv": _to_csv, "xlsx": _to_xlsx, "json": _to_json}


async def export_customers(
    session: AsyncSession,
    *,
    fmt: ExportFormat,
    levels: Sequence[str] | None,
    search: str | None,
    sort: str,
    order: str,
) -> tuple[bytes, str]:
    """Файл выгрузки клиентов под теми же фильтром и сортировкой, что таблица; возвращает (тело, имя файла)"""
    rows = await customer_query.export_customers(session, levels=levels, search=search, sort=sort, order=order)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M")
    return _WRITERS[fmt](rows), f"customers_{stamp}.{fmt}"
