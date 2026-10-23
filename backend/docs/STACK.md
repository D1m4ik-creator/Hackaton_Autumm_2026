# Стек и архитектура

## Стек

| Что | Чем | Зачем |
|---|---|---|
| Web | FastAPI + uvicorn | API, автодокументация на `/docs` |
| БД | PostgreSQL 17: локально в docker (эксперименты) + общая на Supabase | основное хранилище, переключение через `ENV_FILE`, см. README |
| ORM | SQLAlchemy 2.0 async + asyncpg | модели `Mapped[...]`, асинхронные запросы |
| Миграции | Alembic (async env) | схема БД под контролем |
| Валидация и конфиг | pydantic v2, pydantic-settings | схемы запросов/ответов, настройки из `.env` |
| Пароли | pwdlib[argon2] | хэширование (вместо устаревшего passlib) |
| JWT | PyJWT | токены (вместо устаревшего python-jose) |

## Слои (`app/`)

```
main.py          приложение, CORS, подключение роутеров, lifespan
core/config.py   настройки из .env (get_settings)
core/engine.py   engine, сессия, SessionDep
core/security.py хэш паролей, JWT
db/models/       модели SQLAlchemy; Base в base.py; новые модели импортировать в __init__.py
db/schemas/      pydantic-схемы
db/migration/    Alembic
dao/             запросы к БД (BaseDAO + по классу на сущность)
crud/            бизнес-логика над DAO, зависимости (get_current_user и т.п.)
routers/         тонкие эндпоинты
```

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
- URL со слэшем на конце (`/health/`).
- Поля `Config` называются так же, как переменные в `.env` (регистр не важен).
- Секреты только в `.env` (в git не попадает), образец в `.env.example`.

## Авторизация

Перенесена из AuthAPI с правками (pwdlib + PyJWT, refresh хранится хэшем, claim `type`).

| Ручка | Что делает |
|---|---|
| `POST /auth/create_user/` | регистрация (имя, почта, пароль) |
| `POST /auth/login_user/` | логин, ставит cookie `users_access_token` (15 мин) и `users_refresh_token` (30 дней) |
| `POST /auth/refresh/` | новая пара токенов по refresh-cookie |
| `POST /auth/logout/` | выход, сбрасывает refresh в БД и чистит cookie |
| `GET /users/me/` | текущий пользователь |

Защитить свою ручку: `current_user = Depends(crud_user.get_current_user)`.

Фронту: `fetch(..., { credentials: "include" })`, и его адрес должен быть в `CORS_ORIGINS`.

Как работает refresh: в БД лежит хэш последнего выданного refresh-токена. `/refresh/` принимает только его. Старый или чужой токен получает 401 и сбрасывает сессию.

Ограничения: после `logout` access-токен живёт до истечения (до 15 минут); лимита запросов на логин пока нет.
