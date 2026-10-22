# Hackathon Autumn 2026 — backend

FastAPI + async SQLAlchemy + PostgreSQL. Подробности по стеку и слоям: [docs/STACK.md](docs/STACK.md). Работа с ветками в команде: [docs/GIT.md](docs/GIT.md).

## Быстрый старт

```bash
cp .env.example .env            # поправить пароль при необходимости
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

docker compose up -d db         # только база
alembic upgrade head            # миграции
uvicorn app.main:app --reload   # http://localhost:8000/docs
```

Всё в Docker (база + API, миграции применяются при старте):

```bash
docker compose up -d --build
```

## Две базы: локальная и общая (Supabase)

- **Локальная** (Docker, для экспериментов): `.env` — читается по умолчанию.
- **Общая** (Supabase, одна на команду): `.env.shared` (образец — `.env.shared.example`). Включается переменной `ENV_FILE`.

```powershell
# PowerShell: работа с общей базой
$env:ENV_FILE = ".env.shared"
alembic upgrade head
uvicorn app.main:app --reload
Remove-Item Env:ENV_FILE        # вернуться на локальную
```

```bash
# bash
ENV_FILE=.env.shared alembic upgrade head
```

Правила для общей базы:
- `alembic upgrade head` на ней запускает один человек, по договорённости; `downgrade` не запускать без согласования.
- Экспериментировать со схемой только на локальной базе.
- Строка подключения: Supabase -> Database -> **Session pooler** (порт 5432). Transaction pooler (6543) не использовать.
- В Supabase включить RLS на таблицах (без политик) или отключить Data API, иначе таблицы доступны через публичный REST.

## Команды

| Что | Команда |
|---|---|
| Новая миграция | `alembic revision --autogenerate -m "описание"` |
| Применить миграции | `alembic upgrade head` |
| Откатить на шаг | `alembic downgrade -1` |
| Логи API в Docker | `docker compose logs -f api` |
