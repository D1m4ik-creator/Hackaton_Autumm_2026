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

## Вход через Authentik (OIDC), опционально

Локальный логин/пароль выше — основной способ входа и работает всегда. Вместо
него (не вместе) можно включить вход через self-hosted Authentik — OIDC
Authorization Code flow, кнопка на экране логина появляется сама, когда это
включено (`GET /api/v1/auth/oidc/status`).

**Важно**: вход через Authentik пускает только в уже существующий локальный
аккаунт — он ищется по email среди admin/manager, созданных через
`/api/v1/users` (см. «Страница пользователей» в `FRONTEND_TODO.md`). Нет
совпадения по email — понятная ошибка на экране логина, никакой аккаунт
автоматически не создаётся и прав не получает. Суперадмин через OIDC не
заходит (он не хранится в БД и email не имеет) — только локальным паролем.

Настройка:

```bash
docker compose up -d authentik-db authentik-redis authentik-server authentik-worker
```

1. Открыть <http://localhost:9000>, войти бутстрап-админом Authentik
   (`AUTHENTIK_BOOTSTRAP_EMAIL` / `AUTHENTIK_BOOTSTRAP_PASSWORD` из `.env`).
2. Создать **Provider** → OAuth2/OpenID Provider:
   - Authorization flow — `default-provider-authorization-implicit-consent`
     (без лишнего экрана согласия; `explicit-consent` тоже подходит).
   - Client type — **Confidential**.
   - Redirect URI (strict): `http://localhost:8000/api/v1/auth/oidc/callback`
     — должен **точно** совпадать с `OIDC_REDIRECT_URI` в `.env`.
   - **Signing Key** — обязательно выбрать `authentik Self-signed Certificate`
     (или свой). Без ключа `/jwks/` отдаёт пустой список, и колбэк падает с
     `500 KeyError: 'keys'` при попытке проверить подпись `id_token`.
3. Создать **Application**, привязать к этому Provider.
4. На странице Provider — вкладка **Scope Mappings**/Property Mappings:
   добавить `authentik default OAuth Mapping: OpenID 'openid'`, `'email'`,
   `'profile'`. Без них в `id_token`/`userinfo` не будет `email`, и бэкенд не
   сможет сопоставить вход с локальным аккаунтом (отработает как
   `oidc_no_account`, даже если юзер с таким email есть).
   **Важно про `email_verified`**: бэкенд связывает аккаунты только при
   `email_verified: true`, а стандартный маппинг `'email'` в Authentik всегда
   отдаёт `false`. Поэтому вместо него создать свой Scope Mapping
   (Customization → Property Mappings → Scope Mapping, scope name `email`):

   ```python
   return {
       "email": request.user.email,
       "email_verified": True,
   }
   ```

   и подключить его к Provider вместо `authentik default OAuth Mapping: OpenID 'email'`.
   Это безопасно, пока пользователей в Authentik заводит администратор
   (самостоятельная регистрация выключена — так по умолчанию).
5. На странице Provider скопировать `Client ID`, `Client Secret` и ссылку
   `OpenID Configuration Issuer` в `backend/.env`:

   ```env
   OIDC_ENABLED=true
   OIDC_ISSUER=http://authentik-server:9000/application/o/<slug-приложения>/
   OIDC_CLIENT_ID=...
   OIDC_CLIENT_SECRET=...
   # Authentik подставляет в .well-known тот же хост, с которым к нему
   # обратились — бэкенд обращается как authentik-server (имя контейнера),
   # но это браузер не резолвит. Поэтому экран логина (authorization_endpoint)
   # адресуем отдельно, через хост, который резолвится у пользователя:
   OIDC_AUTHORIZE_URL=http://localhost:9000/application/o/authorize/
   ```

6. Пересоздать `api`, чтобы подхватить новые переменные:
   `docker compose up -d --build api`.
7. Включить синхронизацию пользователей: в Authentik создать API-токен админа
   (Directory → Tokens and App passwords → Create, intent **API**) и прописать
   в `backend/.env`:

   ```env
   AUTHENTIK_API_URL=http://authentik-server:9000
   AUTHENTIK_API_TOKEN=...
   ```

   После этого каждый пользователь, созданный админом в панели, сразу появляется
   в Authentik (папка `aeza-panel`) с тем же логином, почтой и паролем; смена
   логина/почты/пароля и удаление тоже повторяются там. Если Authentik недоступен,
   создание и изменение пользователя в панели отвечают `502` и ничего не меняют —
   чтобы пароли не разошлись. Пользователи, созданные до включения синхронизации,
   появятся в Authentik, когда админ задаст им пароль в панели.

   Без синхронизации пользователя нужно завести в Authentik вручную с тем же
   email, что в панели, — иначе вход вернёт «для этого аккаунта нет доступа»
   (`oidc_no_account`).

## Ручки

| Метод и путь | Назначение |
|---|---|
| `POST /api/v1/auth/login` / `refresh` / `logout`, `GET /api/v1/auth/me` | вход, обновление токенов, выход, текущий пользователь |
| `GET /api/v1/auth/oidc/status` | включён ли вход через Authentik (без входа) |
| `GET /api/v1/auth/oidc/login` / `callback` | вход через Authentik: редирект на провайдера и обратно (см. «Вход через Authentik» выше) |
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

## Модель риска

Риск считает логистическая модель (`app/ml/churn_model.py`) через адаптер
контракта `app/analysis/churn.py`: признаки клиента → оценка риска ухода
`score` 0..100 (модель не отвечает «уйдёт/останется», а даёт оценку) и уровень
`high/medium/low` (или `no_data`, если данных нет), плюс денежная оценка
потерь. Веса признаков задаёт пользователь — у модели нет весов по умолчанию;
стартовые значения, пороги уровней, горизонт и момент оценки `asOf` меняются
через `PATCH /api/v1/model/settings` без правки кода. Признаки, формула score
и порогов, формула потерь и таблица настроек — в
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Лимиты и устойчивость

- Тело запроса больше 25 МиБ — `413`, не дочитывая (например, слишком большой снимок).
- Вход под защитой лимитов: по IP (`RATE_LIMIT_LOGIN`/`RATE_LIMIT_REFRESH`) и по
  конкретному логину (`LOGIN_MAX_FAILURES` неудач за `LOGIN_FAILURE_WINDOW_SECONDS`)
  — при срабатывании `429` с `Retry-After`. Отключается `RATE_LIMIT_ENABLED=false`.
- Пока идёт пересчёт, повторный `PATCH /model/settings` или `PUT /source/snapshot`
  ждёт блокировку не дольше `lock_timeout`; не дождавшись — `503` с `Retry-After`.
- Чтения (`/customers`, `/analytics/summary`) идут в одном снимке транзакции
  (`REPEATABLE READ`), поэтому список и сводка на странице согласованы между собой.

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
