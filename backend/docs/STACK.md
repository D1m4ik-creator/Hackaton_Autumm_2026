# Стек и архитектура

## Стек

| Что | Чем | Зачем |
|---|---|---|
| Web | FastAPI + uvicorn | API, автодокументация на `/docs` |
| БД | PostgreSQL 17 в Docker | основное хранилище |
| ORM | SQLAlchemy 2.0 async + asyncpg | модели `Mapped[...]`, асинхронные запросы |
| Миграции | Alembic (async env) | схема БД под контролем |
| Валидация и конфиг | pydantic v2, pydantic-settings | схемы запросов/ответов, настройки из `.env` |
| JWT | PyJWT | токены (вместо устаревшего python-jose) |

## Слои (`app/`)

```
main.py          приложение, CORS, подключение роутеров, lifespan
core/config.py   настройки из .env (get_settings)
core/engine.py   engine, сессия, SessionDep
core/security.py проверка логина и пароля из .env, JWT
db/models/       модели SQLAlchemy; Base в base.py; новые модели импортировать в __init__.py
db/schemas/      pydantic-схемы
db/migration/    Alembic
dao/             запросы к БД (BaseDAO + по классу на сущность)
crud/            бизнес-логика над DAO, зависимости (get_current_user и т.п.)
routers/         тонкие эндпоинты
analysis/        модель риска оттока за интерфейсом (чистый Python, без БД и HTTP)
```

Пакет `analysis/` принадлежит ML-команде: инфраструктура знает только контракт
(`default_settings`, `validate_settings`, `analyze`) и типы из `analysis/types.py`.
Сейчас подключена заглушка `analysis/stub.py`. Подробности — в [ARCHITECTURE.md](ARCHITECTURE.md).

Поток запроса: `router -> crud -> dao -> БД`. Роутер ничего не знает про SQL, DAO ничего не знает про HTTP.

## Как добавить сущность

1. Модель в `app/db/models/<name>.py` (наследник `Base`), импорт в `app/db/models/__init__.py`.
2. Схемы в `app/db/schemas/<name>.py` (`X`, `XCreate`, `XOut`, `model_config = ConfigDict(from_attributes=True)`).
3. `app/dao/<name>.py`: `class XDAO(BaseDAO): model = X`.
4. `app/crud/<name>.py` — логика, если она сложнее одного вызова DAO.
5. `app/routers/<name>.py` — `APIRouter(prefix="/x", tags=["x"])`, подключить в `main.py`.
6. `alembic revision --autogenerate -m "add x"` -> проверить файл -> `alembic upgrade head`.

## Соглашения

- Абсолютные импорты `app.*`, `SessionDep` в сигнатурах.
- Докстринги и сообщения об ошибках на русском.
- JSON в camelCase (ключи схем), деньги — целые евроценты (`int`, в БД `BIGINT`).
- URL без слэша на конце (`/customers`, не `/customers/`). Префикс `/api/v1` для всего, кроме `/metrics`.
- Поля `Config` называются так же, как переменные в `.env` (регистр не важен).
- Секреты только в `.env` (в git не попадает), образец в `.env.example`.

## Авторизация

Публичной регистрации нет. Главный администратор задан в `.env` (`ADMIN_LOGIN`, `ADMIN_PASSWORD`) и в БД не хранится; менеджеров (логин, почта, пароль-argon2) создаёт он через `/api/v1/users`, они лежат в таблице `users`. Роль проверяется на каждом запросе по БД, удалённый менеджер теряет доступ сразу; `require_admin` закрывает ручки администратора (403). Менеджеру доступен только просмотр. Сессия живёт в браузере в двух httpOnly cookie: `users_access_token` (15 минут) и `users_refresh_token` (30 дней). В таблице `auth_sessions` хранится хэш актуального refresh-токена каждой сессии (одна запись на браузер).

| Ручка | Что делает |
|---|---|
| `POST /api/v1/auth/login` | вход (`{"login": "...", "password": "..."}`), создаёт сессию и ставит обе cookie |
| `POST /api/v1/auth/refresh` | новая пара токенов по refresh-cookie; старый refresh больше не действует |
| `GET /api/v1/auth/me` | текущий пользователь (`{"login": "..."}`) |
| `POST /api/v1/auth/logout` | удаляет сессию из БД и cookie |

Замена refresh атомарная. Если тот же старый токен пришёл повторно в течение `JWT_REFRESH_GRACE_SECONDS` (30 секунд) после замены, это параллельный запрос из того же браузера: он получает только новый access. Если давно заменённый токен пришёл позже (например, украденный), сессия закрывается целиком. Просроченные сессии удаляются при каждом входе. После `logout` access-токен живёт до истечения (до 15 минут).

На деплое с HTTPS включить `COOKIE_SECURE=true`.

Защитить свою ручку: `current_user = Depends(crud_auth.get_current_user)`. Фронту: `fetch(..., { credentials: "include" })`, адрес фронта в `CORS_ORIGINS`. Swagger: `/api/v1/docs`.

Локальная база в Docker слушает порт `5433` (5432 часто занят установленным в Windows PostgreSQL).
