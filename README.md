# Hackathon Autumn 2026 — анализатор рисков оттока

Бэкенд (FastAPI + PostgreSQL) и фронт (React). Подробности по бэкенду: [backend/README.md](backend/README.md), архитектура: [backend/docs/ARCHITECTURE.md](backend/docs/ARCHITECTURE.md), ветки: [backend/docs/GIT.md](backend/docs/GIT.md).

## Запуск (Docker)

Нужны Docker и Docker Compose. Из корня репозитория:

```bash
cp backend/.env.example backend/.env
docker compose up -d --build
```

Что произойдёт: поднимется PostgreSQL, `api` применит миграции, загрузит снимок `origin_data/data.json` (10 аккаунтов, 30 услуг, 100 транзакций) в пустую базу и посчитает риск, затем стартует фронт.

| Что | Адрес |
|---|---|
| Фронт | <http://localhost:3000> |
| API, Swagger | <http://localhost:8000/api/v1/docs> |
| Метрики Prometheus | <http://localhost:8000/metrics> |

Вход администратора: `ADMIN_LOGIN` / `ADMIN_PASSWORD` из `backend/.env` (в примере `admin` / `admin12345`). Администратор создаёт менеджеров через `POST /api/v1/users`.

## Перед публикацией на сервере

В `backend/.env` задайте свои значения: `JWT_SECRET_KEY` и `JWT_REFRESH_SECRET_KEY` (разные, от 32 символов; сгенерировать: `python -c "import secrets; print(secrets.token_hex(32))"`), `ADMIN_PASSWORD`, `POSTGRES_PASSWORD`. С `COOKIE_SECURE=true` приложение не стартует, пока в `.env` остаются значения из примера. Для работы по HTTPS поставьте `COOKIE_SECURE=true`, в `CORS_ORIGINS` укажите адрес фронта, а адрес API для фронта задайте через `VITE_API_URL` до сборки.

## Сброс данных

База хранится в томе Docker. Чтобы начать с нуля и заново загрузить `origin_data`:

```bash
docker compose down -v
docker compose up -d --build
```

## Тесты бэкенда

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

Тесты работают в отдельной базе `hackathon_test` (нужна запущенная база из compose, пароль берётся из `POSTGRES_PASSWORD`).
