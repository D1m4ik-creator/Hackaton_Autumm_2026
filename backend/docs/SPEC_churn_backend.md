# Спецификация бэкенда «Анализатор рисков оттока» (инфраструктура)

Объём: только бэкенд-инфраструктура. Фронт и модель риска (признаки, формула score, пороги, формула денег) делают другие участники; для них здесь зафиксирован интерфейс `app/analysis/` и заглушка. Формул модели в этом файле нет.

- База: ветка `feature/churn-analyzer`, голова миграций `55e1b33fc1f7` (`auth_sessions`). Вход готов: `/api/v1/auth/login|me|logout|refresh`, зависимость `crud_auth.get_current_user` (httpOnly cookie).
- Соглашения: слои `core / db(models, schemas, migration) / dao / crud / routers`, поток `router -> crud -> dao`; абсолютные импорты `app.*`; `SessionDep` в ручках; докстринги и ошибки по-русски; JSON в camelCase; деньги — целые евроценты (`int`, в БД `BIGINT`); пути без слэша на конце; префикс `/api/v1` для всего, кроме `/metrics`; Postgres + Alembic.
- Новых зависимостей нет: SSE — `fastapi.sse.EventSourceResponse` (есть в FastAPI 0.159.1), `/metrics` пишем руками.

## 1. Ключевые решения

| # | Решение | Почему |
|---|---|---|
| 1 | Колонки БД в snake_case, camelCase только в pydantic-схемах | Так сделан `auth_sessions`; без кавычек в SQL |
| 2 | Модель риска за интерфейсом `app.analysis`: `analyze()`, `default_settings()`, `validate_settings()` | ML-команда меняет только свой пакет, инфраструктура не трогается |
| 3 | Настройки — один JSONB (`model_settings.data`, строка `id=1`), эффективные = deep-merge `default_settings()` + сохранённое | Структуру задаёт модуль анализа; новый коэффициент появляется без миграции |
| 4 | Результаты материализуются: `risk_results` (по клиенту) + `risk_summary` (одна строка) | Панель, сводка и `/metrics` читают одно и то же, числа совпадают; сортировка в SQL |
| 5 | Замена снимка / сохранение настроек и пересчёт — одна транзакция под `pg_advisory_xact_lock` | Нет гонок и окна «данные новые, результаты старые»; работает и при нескольких процессах |
| 6 | Живое обновление: SSE `GET /api/v1/events`, поток опрашивает `risk_summary.version` раз в секунду | Однонаправленно, cookie уходят сами, нет гонки «событие раньше commit», нет брокера |
| 7 | `/metrics` открыт, только агрегаты | Prometheus не носит cookie; персональных данных нет |
| 8 | Первичная загрузка из `SOURCE_DATA_PATH` в пустую базу при старте; в Docker `../origin_data` монтируется в `/data:ro` | Жюри поднимает всё одной командой, повторный старт данные не трогает |
| 9 | Новые методы DAO не коммитят, коммит делает crud в конце единицы работы | Иначе отпускается advisory-lock и рвётся атомарность |

Из черновиков: snake_case, singleton-сводка (черновик 1); advisory-lock, пересчёт в той же транзакции, три запроса без N+1, сортировка в SQL, 422 с `loc` (черновик 2). Исправлено: in-process брокер SSE (событие могло уйти до commit, не работает при нескольких воркерах) заменён опросом версии; `TRUNCATE` заменён на `DELETE` (не блокирует читателей); SSE не держит `SessionDep` весь поток.

## 2. Файлы

```
backend/app/
  analysis/            __init__.py (точка входа), types.py (вход/выход), churn.py (адаптер модели)
  ml/                  churn_model.py (логистическая модель оттока)
  core/config.py       + source_data_path, seed_on_startup, sse_poll_interval_seconds
  db/models/           account, service, transaction, model_settings, risk_result, risk_summary
  db/schemas/          common (CamelModel), source, customers, analytics, model_settings
  db/migration/versions/2026_10_24_1200-3f9a1c2b7d4e_create_churn_tables.py
  dao/                 base (+bulk), account, service, transaction, model_settings, risk_result, risk_summary, customer_query
  crud/                source, recalc, model_settings, customers, analytics, metrics
  routers/             customers, analytics, model_settings, source, events, metrics
backend/scripts/export_openapi.py, backend/openapi.json
```

## 3. База данных и миграция

Одна ревизия `3f9a1c2b7d4e`, `down_revision = "55e1b33fc1f7"`. Модели наследуют `Base` (naming convention есть), импортируются в `app/db/models/__init__.py`. У `CheckConstraint` короткие `name=`. Даты `DateTime(timezone=True)`. `relationship` не нужны.

`accounts`: `id BIGINT PK (autoincrement=False)`, `email TEXT NOT NULL UNIQUE`, `balance`, `withdraw_balance`, `total_replenished`, `bonus_balance` — `BIGINT NOT NULL CHECK >= 0`, `bonus_state TEXT NOT NULL CHECK IN ('locked','unlocked')`.

`services`: `id BIGINT PK`, `name TEXT NOT NULL`, `owner_id BIGINT NOT NULL FK accounts.id ON DELETE RESTRICT` + индекс, `payment_term TEXT NOT NULL CHECK IN ('hour','week','month','quarter_year','half_year','year')`, `auto_prolong BOOLEAN NOT NULL`, `created_at`, `expires_at TIMESTAMPTZ NOT NULL`, `status TEXT NOT NULL CHECK IN ('active','blocked','deleted','suspended','prolong_wait')`, `price BIGINT NOT NULL CHECK >= 0`.

`transactions`: `id BIGINT PK`, `amount INTEGER NOT NULL CHECK 0..1000`, `status TEXT NOT NULL CHECK IN ('performed','not_performed')`, `performed_at TIMESTAMPTZ NULL`, `created_at TIMESTAMPTZ NOT NULL`, `type TEXT NOT NULL CHECK IN ('prolong','order')`, `service_id BIGINT NOT NULL FK services.id ON DELETE RESTRICT` + индекс.

`model_settings` (одна строка): `id SMALLINT PK CHECK id = 1`, `data JSONB NOT NULL DEFAULT '{}'` (только сохранённое, без дефолтов), `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`.

`risk_results` (строка на клиента):

| колонка | тип | смысл |
|---|---|---|
| account_id | BIGINT | PK, FK accounts.id ON DELETE CASCADE |
| score | SMALLINT NULL | NULL = нет оценки; CHECK 0..100 |
| level | TEXT NOT NULL | CHECK IN ('high','medium','low','no_data'), индекс |
| reason_short | TEXT NOT NULL | текст первой причины, для таблицы |
| reasons | JSONB NOT NULL | `[{"code": "...", "text": "..."}]` |
| expected_loss_cents | BIGINT NOT NULL | CHECK >= 0 |
| details | JSONB NOT NULL DEFAULT '{}' | доп. данные модели для карточки (произвольный JSON) |
| calculated_at | TIMESTAMPTZ NOT NULL | |

Плюс CHECK `(level = 'no_data') = (score IS NULL)`.

`risk_summary` (одна строка, её читают сводка, `/metrics`, SSE): `id SMALLINT PK CHECK id = 1`, `version BIGINT NOT NULL DEFAULT 0` (+1 за пересчёт), `reason TEXT NOT NULL DEFAULT 'init'` (`startup|snapshot|settings`), `customers_total INTEGER NOT NULL DEFAULT 0`, `by_level JSONB NOT NULL DEFAULT '{}'` (`{"high": {"customers": 3, "expectedLossCents": 1200}, "medium": …, "low": …, "no_data": …}`, всегда все 4 ключа), `expected_loss_cents BIGINT NOT NULL DEFAULT 0`, `loss_explanation TEXT NOT NULL DEFAULT ''`, `as_of TIMESTAMPTZ NULL`, `recalculated_at TIMESTAMPTZ NULL`.

После таблиц миграция выполняет `INSERT INTO model_settings (id) VALUES (1); INSERT INTO risk_summary (id) VALUES (1);`. `downgrade` удаляет таблицы в обратном порядке. Можно `alembic revision --autogenerate`, вставки дописать руками, наличие всех CHECK проверить глазами.

DAO. В `app/dao/base.py` добавить (старые методы не трогать; новые **без commit**):

```python
async def load_rows(cls, session) -> Sequence[Row]   # select(cls.model.__table__).order_by(id)
async def bulk_insert(cls, session, rows: list[dict], chunk: int = 5000) -> None
async def delete_all(cls, session) -> None
async def count(cls, session) -> int
```

Классы по файлу: `AccountDAO`, `ServiceDAO`, `TransactionDAO`, `ModelSettingsDAO.get(session) -> dict` / `.save(session, data: dict)`, `RiskResultDAO.replace_all(session, rows)` (DELETE + bulk_insert) / `.get(session, account_id)`, `RiskSummaryDAO.get(session)` / `.save(session, **values) -> int` (`version = version + 1 ... RETURNING version`). Запрос списка клиентов — `dao/customer_query.py` (§8.1).

## 4. Снимок исходных данных

### 4.1 Схемы (`app/db/schemas/common.py`, `app/db/schemas/source.py`)

```python
class CamelModel(BaseModel):
    """Базовая схема API: в Python snake_case, в JSON camelCase"""
    model_config = ConfigDict(alias_generator=to_camel, validate_by_name=True, validate_by_alias=True,
                              serialize_by_alias=True, from_attributes=True)
```

Вход — ровно форма `data.json`; лишние поля игнорируются; дата без зоны = UTC.

| схема | поля (JSON) |
|---|---|
| `SnapshotAccountIn` | `id: int ≥ 1`, `email: str (min 1)`, `balance`, `withdrawBalance`, `totalReplenished`, `bonusBalance: int ≥ 0`, `bonusState: Literal["locked","unlocked"]` |
| `SnapshotServiceIn` | `id`, `name: str`, `ownerId: int`, `paymentTerm: Literal[6]`, `autoProlong: bool` (`AliasChoices("autoProlong","autoprolong")`), `createdAt`, `expiresAt: datetime`, `status: Literal[5]`, `price: int ≥ 0` |
| `SnapshotTransactionIn` | `id`, `amount: int 0..1000`, `status: Literal["performed","not_performed"]`, `performedAt: datetime \| None`, `createdAt: datetime`, `type: Literal["prolong","order"]`, `serviceId: int` |
| `SnapshotIn` | `accounts`, `services`, `transactions` — обязательные списки (пустые допустимы) |
| `SnapshotLoadResult` | `accounts`, `services`, `transactions: int`, `version: int`, `recalculatedAt: datetime` |

Ошибки типов/значений — стандартный 422 FastAPI.

### 4.2 Проверки между записями и замена (`app/crud/source.py`)

```python
def ensure_snapshot_valid(snapshot: SnapshotIn) -> None   # HTTPException(422, detail=[...]) в формате FastAPI, ≤ 50 пунктов
async def replace_source_data(session, snapshot: SnapshotIn) -> SourceCounts   # без commit
def read_snapshot_file(path: Path) -> SnapshotIn | None   # нет файла -> None; невалидный -> ValueError
```

| проверка | пример `loc` | `msg` | `type` |
|---|---|---|---|
| повтор `id` в массиве | `["body","accounts",4,"id"]` | `Повторяется id=5` | `duplicate_id` |
| повтор `email` | `["body","accounts",4,"email"]` | `Email уже есть у аккаунта id=3` | `duplicate_email` |
| нет `ownerId` | `["body","services",13,"ownerId"]` | `Аккаунт ownerId=99 не найден` | `reference_not_found` |
| нет `serviceId` | `["body","transactions",7,"serviceId"]` | `Услуга serviceId=77 не найдена` | `reference_not_found` |
| `performed` без `performedAt` / `not_performed` с ним | `[..., "performedAt"]` | по-русски | `value_error` |

`replace_source_data`: `RiskResultDAO.delete_all` → `TransactionDAO.delete_all` → `ServiceDAO.delete_all` → `AccountDAO.delete_all` → `bulk_insert` accounts → services → transactions. `DELETE`, не `TRUNCATE`: читатели до commit видят старые данные и не блокируются.

### 4.3 Первичная загрузка

Настройки `Config`: `source_data_path: Path = ROOT_DIR.parent / "origin_data" / "data.json"` (`SOURCE_DATA_PATH`), `seed_on_startup: bool = True`. При старте (§6.4), если `accounts` пуста, файл читается, проверяется и грузится. Нет файла или он невалиден — предупреждение в лог, приложение поднимается. Непустая база не трогается.

## 5. Интерфейс модуля анализа (`app/analysis/`)

Чистый Python: без БД, HTTP и SQLAlchemy. Владелец — ML-команда; инфраструктура зависит только от этого контракта.

`app/analysis/types.py`:

```python
Level = Literal["high", "medium", "low", "no_data"]

@dataclass(frozen=True)
class AccountData:  id: int; email: str; balance: int; withdraw_balance: int; total_replenished: int; bonus_balance: int; bonus_state: str
@dataclass(frozen=True)
class ServiceData:  id: int; name: str; owner_id: int; payment_term: str; auto_prolong: bool; created_at: datetime; expires_at: datetime; status: str; price: int
@dataclass(frozen=True)
class TransactionData: id: int; amount: int; status: str; performed_at: datetime | None; created_at: datetime; type: str; service_id: int

@dataclass(frozen=True)
class SourceData:
    accounts: list[AccountData]; services: list[ServiceData]; transactions: list[TransactionData]

@dataclass(frozen=True)
class Reason:
    code: str          # машинный код причины
    text: str          # понятная фраза по-русски

@dataclass(frozen=True)
class CustomerRisk:
    account_id: int
    score: int | None              # 0..100; None только при level = "no_data"
    level: Level
    reasons: list[Reason]          # первая — главная (идёт в reasonShort)
    expected_loss_cents: int       # ≥ 0, целые евроценты
    details: dict = field(default_factory=dict)   # JSON-сериализуемое, отдаётся в карточке как есть

@dataclass(frozen=True)
class AnalysisResult:
    customers: list[CustomerRisk]
    loss_explanation: str          # смысл денежной суммы для панели
```

`app/analysis/__init__.py` — единственная точка входа (импортирует реализацию; сейчас из адаптера `churn.py`):

```python
def default_settings() -> dict          # настройки по умолчанию, JSON-сериализуемые
def validate_settings(data: dict) -> dict   # нормализует; ошибка -> ValueError("понятный текст")
def analyze(source: SourceData, settings: dict, as_of: datetime) -> AnalysisResult
```

Правила для инфраструктуры:
- `settings` всегда прошёл `validate_settings`. `as_of`: если в настройках есть ключ `asOf` со строкой ISO-8601 — она, иначе `datetime.now(timezone.utc)`. Фактический `as_of` пишется в `risk_summary.as_of`.
- Проверка результата (`crud/recalc.py::check_result`): `score` int 0..100 или `None`; `None` ⇔ `no_data`; `expected_loss_cents` int ≥ 0; `account_id` из снимка, без повторов. Клиент без результата → `no_data`, причина «Модель не вернула оценку». Нарушение контракта → `AnalysisContractError` (транзакция откатывается, ответ 500 «Ошибка модели анализа: …»).
- `analyze` вызывается через `asyncio.to_thread` — не блокирует цикл событий.

Реализация (подключена): адаптер `app/analysis/churn.py` поверх логистической модели `app/ml/churn_model.py`. `default_settings()` отдаёт `asOf`, веса признаков, `bias`, `threshold`, пороги уровней, `expiresSoonDays`, `horizonDays`; `validate_settings` нормализует присутствующие ключи и сохраняет неизвестные; `analyze` переводит вероятность оттока в `score` 0..100 и уровень `high/medium/low`, считает денежную оценку потерь, а клиентам без услуг и транзакций ставит `no_data`. Признаки, формула score и порогов, формула потерь и таблица настроек — в [ARCHITECTURE.md](ARCHITECTURE.md).

Как расширять модель: добавить признак в `extract_features` (`app/ml/churn_model.py`) и вес в `default_settings()` или через `PATCH /model/settings`; БД, ручки и фронт-контракт не меняются (настройки — JSON, причины и `details` — списки/объекты).

## 6. Пересчёт

### 6.1 Когда

| событие | где | `reason` |
|---|---|---|
| старт приложения (всегда, после первичной загрузки) | lifespan → `crud.recalc.startup` | `startup` |
| `PUT /source/snapshot` | та же транзакция, что замена | `snapshot` |
| `PATCH /model/settings` | та же транзакция, что сохранение | `settings` |

### 6.2 Интерфейс `app/crud/recalc.py`

```python
RECALC_LOCK_KEY = 815_007_001

async def acquire_lock(session) -> None              # SELECT pg_advisory_xact_lock(:key); снимается на commit/rollback
async def effective_settings(session) -> dict        # validate_settings(deep_merge(default_settings(), ModelSettingsDAO.get()))
async def recalculate(session, reason: str) -> RiskSummary   # в текущей транзакции; lock и commit — у вызывающего
async def apply_snapshot(session, snapshot) -> SnapshotLoadResult   # ensure_valid -> lock -> replace -> recalculate -> commit
async def startup(session) -> None                   # lock -> seed если пусто -> recalculate('startup') -> commit
```

`deep_merge`: словари сливаются рекурсивно, остальные значения заменяются целиком. Если сохранённые настройки после обновления модели перестали проходить `validate_settings` — в лог предупреждение и пересчёт на `default_settings()` (строка в БД не трогается).

### 6.3 Алгоритм `recalculate`

1. `settings = effective_settings()`, `as_of` по §5.
2. Три запроса `load_rows` (accounts, services, transactions) → `SourceData` (без N+1).
3. `result = await asyncio.to_thread(analysis.analyze, source, settings, as_of)` → `check_result`.
4. `RiskResultDAO.replace_all` строками `{account_id, score, level, reason_short=reasons[0].text или "", reasons=[{code,text}], expected_loss_cents, details, calculated_at=now}`.
5. Сводка: `customers_total`, `by_level` (число клиентов и Σ `expected_loss_cents` по каждому из 4 уровней), `expected_loss_cents` = Σ по клиентам (сумма строк = числу в сводке и `/metrics`), `loss_explanation`, `as_of`, `recalculated_at=now`, `reason` → `RiskSummaryDAO.save` → новый `version`.

### 6.4 Гонки и старт

- Все записи исходных данных, настроек и результатов — под `pg_advisory_xact_lock(RECALC_LOCK_KEY)`; одновременные PATCH/PUT/старт второго воркера идут по очереди, второй ждёт.
- Данные и результаты меняются в одной транзакции: читатель (READ COMMITTED) видит либо всё старое, либо всё новое. Отдельные SELECT одной ручки могут попасть на разные commit — допустимо, следующее SSE-событие перезапросит.
- PATCH сливает и валидирует настройки **после** взятия блокировки (два PATCH не теряют друг друга).
- Lifespan: `async with SessionLocal() as s: await crud_recalc.startup(s)` в `try/except` с `logger.exception` — API поднимается даже при ошибке; затем `yield`, затем `close_engine()`.

## 7. Живое обновление (SSE)

`GET /api/v1/events`, `response_class=EventSourceResponse` из `fastapi.sse` (сам ставит `text/event-stream`, `Cache-Control: no-cache`, шлёт keep-alive). Защищён `get_current_user`: браузерный `EventSource` отправляет httpOnly cookie сам (другой origin — `withCredentials: true`, CORS с `allow_credentials` уже включён). WebSocket не нужен: поток односторонний.

Реализация (`app/routers/events.py`, генератор):
- **Без `SessionDep`** (держал бы соединение весь поток): на каждой итерации короткая `async with SessionLocal() as s: RiskSummaryDAO.get(s)`.
- Первое сообщение `retry: 3000`, затем `ready` с текущей версией (или `recalculated`, если заголовок `Last-Event-ID` отличается от версии). Дальше раз в `SSE_POLL_INTERVAL_SECONDS` (1) при смене `version` → `recalculated`. `id` события = `version`.
- Каждую итерацию `await request.is_disconnected()`; поток закрывается сервером, когда истекает access-токен (`exp` из `access_decode_token(get_token(request))`), браузер переподключается.

```
retry: 3000

event: ready
id: 3
data: {"version": 3, "reason": "startup", "recalculatedAt": "2026-10-24T12:00:00Z"}

event: recalculated
id: 4
data: {"version": 4, "reason": "settings", "recalculatedAt": "2026-10-24T12:05:10Z"}
```

Фронту: на `recalculated` перезапросить сводку, текущую страницу таблицы и открытую карточку; при `readyState === CLOSED` (401) — `POST /api/v1/auth/refresh` и новый `EventSource`.

## 8. Контракт API

Все ручки, кроме `/metrics`, под `/api/v1`; роутеры создаются с `dependencies=[Depends(crud_auth.get_current_user)]` (ни одну не забыть). Без/с битой cookie — `401` (тексты из `core/security.py`). Ответы camelCase, деньги в евроцентах, даты ISO-8601 UTC. Содержимое `settings` и `details` отдаётся как есть (ключи задаёт модуль анализа, не переименовываются).

| метод и путь | ответ | ошибки |
|---|---|---|
| `GET /customers` | `CustomerPage` | 401, 422 |
| `GET /customers/{customerId}` | `CustomerCard` | 401, 404, 422 |
| `GET /analytics/summary` | `SummaryOut` | 401 |
| `GET /model/settings` | `ModelSettingsOut` | 401 |
| `PATCH /model/settings` | `ModelSettingsOut` | 401, 422, 500 |
| `PUT /source/snapshot` | `SnapshotLoadResult` | 401, 422, 500 |
| `GET /events` | `text/event-stream` | 401 |
| `GET /metrics` | `text/plain` | — |

### 8.1 `GET /customers`

| query | значения | по умолчанию |
|---|---|---|
| `level` | `high`, `medium`, `low`, `no_data`; можно несколько (`?level=high&level=medium`) | все |
| `search` | подстрока email без учёта регистра (`ilike`, с экранированием `%_`); если только цифры — ещё и точный `id` | — |
| `sort` | `id`, `email`, `balance`, `totalReplenished`, `riskScore`, `expectedLossCents` | `riskScore` |
| `order` | `asc`, `desc` | `desc` |
| `page` / `pageSize` | ≥ 1 / 1..200 | 1 / 50 |

`dao/customer_query.py`: `accounts LEFT JOIN risk_results`, колонка сортировки из белого списка, `NULLS LAST` в обе стороны (без оценки — внизу), вторичный ключ `accounts.id ASC`; `total` — `count` с тем же фильтром. Нет строки в `risk_results` → `level: "no_data"`, `riskScore: null`.

```json
{"items": [
   {"id": 5, "email": "user-0005@example.test", "balance": 28657, "totalReplenished": 293608,
    "riskScore": null, "level": "no_data", "expectedLossCents": 0,
    "reasonShort": "Модель анализа ещё не подключена"}],
 "total": 10, "page": 1, "pageSize": 50}
```

### 8.2 `GET /customers/{customerId}`

404 `{"detail": "Клиент не найден"}`.

```json
{"id": 5, "email": "user-0005@example.test", "balance": 28657, "withdrawBalance": 7623,
 "totalReplenished": 293608, "bonusBalance": 9863, "bonusState": "locked",
 "riskScore": null, "level": "no_data", "expectedLossCents": 0,
 "reasonShort": "Модель анализа ещё не подключена",
 "reasons": [{"code": "model_not_connected", "text": "Модель анализа ещё не подключена"}],
 "details": {},
 "services": [{"id": 5, "name": "service-0005", "status": "prolong_wait", "price": 748, "autoProlong": false,
               "paymentTerm": "half_year", "createdAt": "2025-09-14T15:00:00Z", "expiresAt": "2026-03-14T15:00:00Z"}],
 "transactions": {"total": 10, "performed": 7, "notPerformed": 3},
 "asOf": "2026-10-24T12:00:00Z", "calculatedAt": "2026-10-24T12:00:00Z"}
```

### 8.3 `GET /analytics/summary`

```json
{"customersTotal": 10,
 "byLevel": {"high": {"customers": 0, "expectedLossCents": 0}, "medium": {"customers": 0, "expectedLossCents": 0},
             "low": {"customers": 0, "expectedLossCents": 0}, "noData": {"customers": 10, "expectedLossCents": 0}},
 "expectedLossCents": 0,
 "lossExplanation": "Модель анализа ещё не подключена, денежная оценка не считается",
 "asOf": "2026-10-24T12:00:00Z", "recalculatedAt": "2026-10-24T12:00:00Z", "version": 3}
```

### 8.4 `GET` / `PATCH /model/settings`

GET: `{"settings": {...эффективные...}, "defaults": {...default_settings()...}, "updatedAt": "..."}`.

PATCH: тело — JSON-объект (частичный), deep-merge с текущими эффективными → `validate_settings` → сохранить `data` → `recalculate('settings')` → commit, всё под lock. Ответ — как GET плюс `"version": 4, "recalculatedAt": "..."`. Тело не объект или `ValueError` модели → `422 {"detail": [{"loc": ["body"], "msg": "<текст модели>", "type": "value_error"}]}`.

```json
{"asOf": "2026-10-19T15:00:00Z"}
```

### 8.5 `PUT /source/snapshot`

Тело — как `data.json` (§4.1). Полная замена + пересчёт в одной транзакции (§6). Ответ:

```json
{"accounts": 10, "services": 30, "transactions": 100, "version": 5, "recalculatedAt": "2026-10-24T12:10:00Z"}
```

Ошибки: 422 (схема или §4.2, старые данные целы), 500 (контракт модели нарушен, откат).

## 9. `/metrics` (Prometheus)

`GET /metrics` — без префикса, **без входа** (скрейпер не носит cookie; только агрегаты, без email/id/балансов, `include_in_schema=False` не ставим — пусть видно в Swagger). `PlainTextResponse`, `Content-Type: text/plain; version=0.0.4; charset=utf-8`. Все числа из той же строки `risk_summary`, что и `/analytics/summary`; все 4 уровня выводятся всегда, до первого пересчёта — нули. Текст собирает `app/crud/metrics.py::render_metrics(session) -> str`.

```
# HELP churn_customers Количество клиентов по уровню риска
# TYPE churn_customers gauge
churn_customers{level="high"} 0
churn_customers{level="medium"} 0
churn_customers{level="low"} 0
churn_customers{level="no_data"} 10
# HELP churn_expected_loss_eurocents Ожидаемые потери, евроценты
# TYPE churn_expected_loss_eurocents gauge
churn_expected_loss_eurocents 0
# HELP churn_expected_loss_by_level_eurocents Ожидаемые потери по уровню риска, евроценты
# TYPE churn_expected_loss_by_level_eurocents gauge
churn_expected_loss_by_level_eurocents{level="high"} 0
churn_expected_loss_by_level_eurocents{level="medium"} 0
churn_expected_loss_by_level_eurocents{level="low"} 0
churn_expected_loss_by_level_eurocents{level="no_data"} 0
# HELP churn_last_recalculation_timestamp_seconds Время последнего пересчёта, unixtime
# TYPE churn_last_recalculation_timestamp_seconds gauge
churn_last_recalculation_timestamp_seconds 1792843200
# HELP churn_recalculations_total Число пересчётов
# TYPE churn_recalculations_total counter
churn_recalculations_total 3
```

`churn_recalculations_total` = `risk_summary.version`. Строка заканчивается `\n`.

## 10. OpenAPI, Docker, README

- `backend/scripts/export_openapi.py`: `from app.main import app`; `json.dump(app.openapi(), f, ensure_ascii=False, indent=2)` в `backend/openapi.json`. Импорт `app.main` требует `.env` (engine создаётся при импорте, но к базе не подключается). Запуск: `python scripts/export_openapi.py` или `docker compose exec api python scripts/export_openapi.py`. Файл коммитится; живая схема — `/api/v1/openapi.json`, Swagger — `/api/v1/docs`.
- `docker-compose.yaml`, сервис `api`:

```yaml
    volumes:
      - ../origin_data:/data:ro
    environment:
      POSTGRES_HOST: db
      POSTGRES_PORT: 5432
      SOURCE_DATA_PATH: /data/data.json
```

- `Dockerfile` не меняется: `alembic upgrade head && uvicorn ...`; загрузка и пересчёт — в lifespan. `origin_data/` лежит в корне git-репозитория и должен быть закоммичен (сейчас не отслеживается).
- `.env.example`: `SOURCE_DATA_PATH`, `SEED_ON_STARTUP=true`, `SSE_POLL_INTERVAL_SECONDS=1`.
- `docs/STACK.md`: исправить «URL со слэшем на конце» на «без слэша»; добавить слой `analysis/`.
- `README.md` (для жюри): `cp .env.example .env` → `docker compose up -d --build` → Swagger `http://localhost:8000/api/v1/docs`, вход логином из `.env`; список ручек; `/metrics`; как загрузить свой снимок (`PUT /api/v1/source/snapshot`); живое обновление; ссылка на `docs/ARCHITECTURE.md`.
- `docs/ARCHITECTURE.md`: слои и поток данных (снимок → пересчёт → `risk_results`/`risk_summary` → API/SSE/metrics), гонки, интерфейс `app/analysis`, «как добавить признак» (§5), место для описания модели от ML-команды.

## 11. Пакеты работ

Пути от корня репозитория. Списки файлов не пересекаются.

**P1 — Хранилище и снимок** (зависимостей нет). Файлы: `backend/app/core/config.py`, `backend/app/db/models/__init__.py`, `backend/app/db/models/{account,service,transaction,model_settings,risk_result,risk_summary}.py`, `backend/app/db/migration/versions/2026_10_24_1200-3f9a1c2b7d4e_create_churn_tables.py`, `backend/app/db/schemas/common.py`, `backend/app/db/schemas/source.py`, `backend/app/dao/base.py`, `backend/app/dao/{account,service,transaction,model_settings,risk_result,risk_summary}.py`, `backend/app/crud/source.py`. Сделать §3, §4, поля `Config` (§4.3, §7). Проверка: `alembic upgrade head` и `downgrade -1` на локальной базе (порт 5433), CHECK на месте.

**P2 — Интерфейс анализа и пересчёт** (зависит от P1). Файлы: `backend/app/analysis/__init__.py`, `backend/app/analysis/types.py`, `backend/app/analysis/churn.py` (адаптер) и `backend/app/ml/churn_model.py` (модель), `backend/app/crud/recalc.py`. Сделать §5, §6. Проверка: скриптом на локальной базе `startup()` на пустой базе грузит `origin_data/data.json`, клиенты получают `score` и уровни риска, `version` растёт; два параллельных `apply_snapshot` выполняются по очереди.

**P3 — API, SSE, metrics** (зависит от P1, P2). Файлы: `backend/app/db/schemas/{customers,analytics,model_settings}.py`, `backend/app/dao/customer_query.py`, `backend/app/crud/{customers,analytics,model_settings,metrics}.py`, `backend/app/routers/{customers,analytics,model_settings,source,events,metrics}.py`, `backend/app/main.py` (роутеры: `/metrics` без префикса, остальные с `API_PREFIX`; lifespan из §6.4). Сделать §7, §8, §9. Проверка: без cookie все ручки, кроме `/metrics`, дают 401; сортировка по каждому полю в обе стороны; PATCH и PUT поднимают `version`, открытый `/events` присылает `recalculated`; суммы `/metrics` = `/analytics/summary`.

**P4 — Документация, Docker, OpenAPI** (зависит от P1–P3). Файлы: `backend/docker-compose.yaml`, `backend/.env.example`, `backend/README.md`, `backend/docs/STACK.md`, `backend/docs/ARCHITECTURE.md`, `backend/scripts/export_openapi.py`, `backend/openapi.json`. Сделать §10; закоммитить `origin_data/`. Проверка: с чистого `docker compose down -v && docker compose up -d --build` по README — вход, `GET /api/v1/customers` отдаёт 10 клиентов, `/metrics` отвечает.

## 12. Открытые вопросы

- Контракт `app.analysis` согласовать с ML-командой до начала P2 (особенно ключ `asOf` в настройках и формат `details`).
- Нужен ли пересчёт при прямых правках БД (мимо `PUT /source/snapshot`)? Сейчас нет; при необходимости — триггер-счётчик ревизий и фоновый наблюдатель.
- Нужен ли фронту список признаков/описание настроек для формы (`settingsSchema` от модуля анализа)? Сейчас фронт получает `settings` и `defaults` как JSON.
