"""Экспорт схемы OpenAPI в backend/openapi.json.

Запуск с хоста из каталога backend (внутри контейнера каталог только для чтения):
    python scripts/export_openapi.py

Импорт ``app.main`` требует заполненного .env (движок БД создаётся при импорте,
но подключение к базе не выполняется).
"""

import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
# Чтобы скрипт работал из любого каталога (python scripts/export_openapi.py)
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402

OUTPUT_PATH = BACKEND_DIR / "openapi.json"


def main() -> None:
    """Собирает схему приложения и пишет её в openapi.json (UTF-8, с отступами)."""
    schema = app.openapi()
    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(schema, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(f"OpenAPI сохранён: {OUTPUT_PATH} ({len(schema.get('paths', {}))} путей)")


if __name__ == "__main__":
    main()
