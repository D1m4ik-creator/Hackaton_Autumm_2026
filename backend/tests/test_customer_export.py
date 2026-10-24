"""Выгрузка клиентов: CSV/Excel/JSON с фильтром и сортировкой как у списка."""

import csv
import io
import json
from pathlib import Path

import pytest
from httpx import AsyncClient
from openpyxl import load_workbook

from app.crud.customer_export import HEADERS

SNAPSHOT = json.loads(
    (Path(__file__).resolve().parents[2] / "origin_data" / "data.json").read_text(encoding="utf-8")
)
ADMIN = {"login": "admin", "password": "test_password"}


@pytest.fixture
async def loaded(client: AsyncClient) -> AsyncClient:
    assert (await client.post("/api/v1/auth/login", json=ADMIN)).status_code == 200
    assert (await client.put("/api/v1/source/snapshot", json=SNAPSHOT)).status_code == 200
    return client


async def _list_ids(client: AsyncClient, query: str = "") -> list[int]:
    page = (await client.get(f"/api/v1/customers?pageSize=200&{query}")).json()
    return [c["id"] for c in page["items"]]


async def test_export_csv_matches_list_order(loaded: AsyncClient):
    response = await loaded.get("/api/v1/customers/export?format=csv&sort=balance&order=asc")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert 'filename="customers_' in response.headers["content-disposition"]
    assert response.content.startswith("﻿".encode())

    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig")), delimiter=";"))
    assert rows[0] == HEADERS
    assert [int(r[0]) for r in rows[1:]] == await _list_ids(loaded, "sort=balance&order=asc")


async def test_export_xlsx_has_header_and_all_rows(loaded: AsyncClient):
    response = await loaded.get("/api/v1/customers/export?format=xlsx")
    assert response.status_code == 200
    sheet = load_workbook(io.BytesIO(response.content)).active
    values = list(sheet.iter_rows(values_only=True))
    assert list(values[0]) == HEADERS
    assert [r[0] for r in values[1:]] == await _list_ids(loaded)
    # Деньги в евро, а не в центах
    first = (await loaded.get(f"/api/v1/customers/{values[1][0]}")).json()
    assert values[1][5] == round(first["balance"] / 100, 2)


async def test_export_json_respects_filters(loaded: AsyncClient):
    response = await loaded.get("/api/v1/customers/export?format=json&search=0003")
    assert response.status_code == 200
    items = response.json()["items"]
    assert [i["id"] for i in items] == [3]
    assert set(items[0]) >= {"email", "level", "riskScore", "balance", "withdrawBalance", "bonusState"}


async def test_export_validation_and_auth(loaded: AsyncClient):
    assert (await loaded.get("/api/v1/customers/export?format=pdf")).status_code == 422
    await loaded.post("/api/v1/auth/logout")
    loaded.cookies.clear()
    assert (await loaded.get("/api/v1/customers/export")).status_code == 401
