# Анализатор рисков оттока — backend

FastAPI + async SQLAlchemy + PostgreSQL. Бэкенд считает риск оттока клиентов по
снимку данных хостинга и отдаёт панели список клиентов, сводку, настройки модели,
живое обновление и метрики Prometheus.

Архитектура, слои и интерфейс модели — [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
Стек и соглашения — [docs/STACK.md](docs/STACK.md). Работа с ветками — [docs/GIT.md](docs/GIT.md).

## Запуск для жюри (одна команда)

```bash
cp .env.example .env            # при желании поменять ADMIN_LOGIN/ADMIN_PASSWORD
docker compose up -d --build
```

Поднимаются два контейнера: `db` (PostgreSQL, порт 5433 на хосте) и `api`
(порт 8000). При старте `api` применяет миграции, грузит снимок
`origin_data/data.json` (примонтирован в `/data:ro`) в пустую базу и считает риск.
Повторный старт данные не трогает.

Каталог `origin_data/` должен лежать в корне репозитория (рядом с `backend/`) —
без него база поднимется пустой, а сводка будет нулевой.

- Swagger: <http://localhost:8000/api/v1/docs>
- Схема OpenAPI: <http://localhost:8000/api/v1/openapi.json> (копия в [openapi.json](openapi.json))
- Логи: `docker compose logs -f api`

## Вход

Три роли (иерархия):

- **Суперадмин** — один, задаётся в `.env` (`ADMIN_LOGIN` / `ADMIN_PASSWORD`, по умолчанию `admin` / `admin12345`), в базе не хранится. Создаёт и удаляет админов и менеджеров (`/api/v1/users`, для админа в теле `"role": "admin"`), меняет настройки модели и загружает снимок данных.
- **Админ** — создаёт суперадмин (логин, почта, пароль). Видит и ведёт **всех менеджеров** (создаёт, меняет, удаляет), меняет настройки модели и загружает снимок данных. Админов создавать и менять не может.
- **Менеджер** — создаёт админ или суперадмин, передаёт ему логин и пароль. Входит по логину или почте, видит клиентов, карточки, сводку и настройки модели (только просмотр). Остальное — `403`.

Сессия — две httpOnly cookie, их ставит
`POST /api/v1/auth/login`. В Swagger: выполнить `auth/login` с телом
`{"login": "admin", "password": "admin12345"}` — cookie сохранятся в браузере,
остальные ручки станут доступны.

Ручки под `/api/v1` требуют валидной cookie — без неё `401`. Без входа открыты
`/metrics`, `/api/v1/health` и `auth/login` | `auth/refresh`.

## Ручки

| Метод и путь | Назначение |
|---|---|
| `POST /api/v1/auth/login` / `refresh` / `logout`, `GET /api/v1/auth/me` | вход, обновление токенов, выход, текущий пользователь |
| `GET /api/v1/customers` | список клиентов: фильтр `level`, поиск `search`, сортировка `sort`/`order`, пагинация `page`/`pageSize` |
| `GET /api/v1/customers/{customerId}` | карточка клиента: причины, услуги, транзакции |
| `GET /api/v1/analytics/summary` | сводка: клиенты по уровням, ожидаемые потери, версия |
| `GET /api/v1/model/settings` | эффективные настройки модели + дефолты |
| `PATCH /api/v1/model/settings` | частично поменять настройки (deep-merge) и пересчитать; суперадмин и админ |
| `DELETE /api/v1/model/settings/{section}/{key}` | удалить пункт настроек, например признак модели `weights/имя`, и пересчитать; 404 если пункта нет; суперадмин и админ |
| `PUT /api/v1/source/snapshot` | загрузить свой снимок и пересчитать; суперадмин и админ |
| `GET /api/v1/events` | живое обновление (SSE) |
| `GET`/`POST /api/v1/users`, `PATCH`/`DELETE /api/v1/users/{userId}` | пользователи: список, создание (логин, почта, пароль; `role: admin` только суперадмин), изменение, удаление; суперадмин и админы, админ работает только с менеджерами |
| `GET /api/v1/health` | проверка живости API и базы (без входа) |
| `GET /metrics` | метрики Prometheus (без входа) |

## Метрики

`GET http://localhost:8000/metrics` — текст в формате Prometheus (без cookie,
только агрегаты, без email/id/балансов). Числа берутся из той же строки сводки,
что и `/analytics/summary`, поэтому совпадают. До первого пересчёта — нули.

## Загрузка своего снимка

`PUT /api/v1/source/snapshot`, тело — как `origin_data/data.json`
(`{"accounts": [...], "services": [...], "transactions": [...]}`). Полная замена
данных и пересчёт идут в одной транзакции: при ошибке схемы или ссылок —
`422`, старые данные целы. Ответ — число загруженных сущностей и новая `version`.

## Живое обновление

`GET /api/v1/events` — поток Server-Sent Events. После каждого пересчёта
(загрузка снимка, изменение настроек, старт) приходит событие `recalculated` с
новой `version`. Фронт на него перезапрашивает сводку, текущую страницу таблицы и
открытую карточку. Браузерный `EventSource` сам шлёт cookie; при закрытии потока
по истечении access-токена — `POST /api/v1/auth/refresh` и новый `EventSource`.

## OpenAPI

Статичная копия схемы — [openapi.json](openapi.json). Перегенерировать:

```bash
python scripts/export_openapi.py
```

## Разработка (без Docker)

```bash
cp .env.example .env
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt

docker compose up -d db         # только база (порт 5433)
alembic upgrade head
uvicorn app.main:app --reload   # http://localhost:8000/api/v1/docs
```

## Команды

| Что | Команда |
|---|---|
| Новая миграция | `alembic revision --autogenerate -m "описание"` |
| Применить миграции | `alembic upgrade head` |
| Откатить на шаг | `alembic downgrade -1` |
| Логи API в Docker | `docker compose logs -f api` |
| Экспорт OpenAPI | `python scripts/export_openapi.py` |
