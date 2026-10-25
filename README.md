# Hackathon Autumn 2026 — анализатор рисков оттока

Бэкенд (FastAPI + PostgreSQL) и фронт (React). Подробности по бэкенду: [backend/README.md](backend/README.md), архитектура: [backend/docs/ARCHITECTURE.md](backend/docs/ARCHITECTURE.md), ветки: [backend/docs/GIT.md](backend/docs/GIT.md).

## Запуск (Docker)

Нужны Docker и Docker Compose. Из корня репозитория:

```bash
cp backend/.env.example backend/.env
docker compose up -d --build
```

Что произойдёт: поднимется PostgreSQL, `api` применит миграции, загрузит снимок `origin_data/data.json` (10 аккаунтов, 30 услуг, 100 транзакций) в пустую базу и посчитает риск, затем стартует фронт, Prometheus и Grafana.

| Что | Адрес |
|---|---|
| Фронт | <http://localhost> |
| API, Swagger | <http://localhost:8000/api/v1/docs> |
| Метрики Prometheus (сырой текст) | <http://localhost:8000/metrics> |
| Grafana (дашборды и алерты, см. [ops/README.md](ops/README.md)) | <http://localhost:3001> |

https://www.full-stack-hack.ru

Вход суперадминистратора: логин `superadmin`, пароль `FoolStack2026`. Учётные данные задаются через `ADMIN_LOGIN` / `ADMIN_PASSWORD` в `backend/.env`. Администратор создаёт менеджеров через `POST /api/v1/users`.

В меню «Загрузить снимок» доступны JSON, Excel (`.xlsx`) и CSV (`.csv`), в режимах замены и добавления. Новые выгрузки клиентов во всех трёх форматах содержат исходные аккаунты, услуги и транзакции и подходят для обратной загрузки. Старые CSV/Excel с одним отчётом нужно выгрузить заново: в них нет услуг и транзакций для восстановления снимка.

Помимо оценки риска и денег под риском панель умеет: журнал изменений
настроек модели (кто/когда/что поменял — «История изменений» в сайдбаре),
быстрая сортировка клиентов по приоритету вмешательства (кнопка
«Приоритет» над таблицей) и публичные read-only ссылки на отчёт без логина
и без email клиентов («Поделиться отчётом» в сайдбаре) — подробности в
[backend/README.md](backend/README.md#аудит-изменений-настроек).

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
