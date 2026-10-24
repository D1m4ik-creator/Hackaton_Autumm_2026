# Архитектура «Анализатора рисков оттока»

Бэкенд считает риск оттока клиентов по снимку данных хостинга, материализует
результаты в базе и отдаёт их панели, метрикам и живому обновлению. Полная
спецификация — [SPEC_churn_backend.md](SPEC_churn_backend.md); стек и соглашения —
[STACK.md](STACK.md).

## Слои

Поток запроса — `router -> crud -> dao -> БД`. Роутер не знает про SQL, DAO не
знает про HTTP.

```
app/
  core/        config (настройки из .env), engine (SessionLocal, SessionDep), security (JWT, вход)
  db/models/   таблицы SQLAlchemy (Base + naming convention)
  db/schemas/  pydantic-схемы API; CamelModel: snake_case в Python, camelCase в JSON
  db/migration три ревизии: auth_sessions, churn-таблицы, users
  dao/         запросы к БД; новые методы без commit (коммитит crud в конце единицы работы)
  crud/        бизнес-логика: source (замена снимка), recalc (пересчёт), customers, analytics, model_settings, metrics
  routers/     тонкие эндпоинты; все под /api/v1 с авторизацией, кроме /metrics
  analysis/    модель риска за интерфейсом (чистый Python, без БД и HTTP) — зона ML-команды
```

## Поток данных

```
снимок (origin_data/data.json или PUT /source/snapshot)
   │  crud.source.replace_source_data: DELETE старых + bulk_insert новых
   ▼
accounts / services / transactions
   │  crud.recalc.recalculate: load_rows -> SourceData -> analysis.analyze (asyncio.to_thread) -> check_result
   ▼
risk_results (строка на клиента)  +  risk_summary (одна строка, version += 1)
   │
   ├─ GET /customers, /customers/{id}   — accounts LEFT JOIN risk_results, сортировка и пагинация в SQL
   ├─ GET /analytics/summary            — risk_summary
   ├─ GET /metrics                      — risk_summary (те же числа, формат Prometheus)
   └─ GET /events (SSE)                 — опрос risk_summary.version раз в секунду
```

Результаты материализованы: сводка, таблица и `/metrics` читают одну и ту же
строку `risk_summary`, поэтому числа всегда совпадают.

### Когда происходит пересчёт

| Событие | Где | `reason` |
|---|---|---|
| старт приложения (после первичной загрузки) | lifespan → `crud.recalc.startup` | `startup` |
| `PUT /source/snapshot` | та же транзакция, что замена | `snapshot` |
| `PATCH /model/settings` | та же транзакция, что сохранение | `settings` |

Первичная загрузка: при старте, если `accounts` пуста, читается
`SOURCE_DATA_PATH` (в Docker — `/data/data.json`), проверяется и грузится. Нет
файла или он невалиден — предупреждение в лог, API всё равно поднимается.
Непустая база не трогается.

## Гонки и согласованность

- Все записи снимка, настроек и результатов идут под
  `pg_advisory_xact_lock(RECALC_LOCK_KEY)`. Одновременные `PATCH`/`PUT`/старт
  второго воркера выстраиваются в очередь — второй ждёт, а не затирает первого.
  Блокировка снимается автоматически на commit/rollback.
- Замена данных и пересчёт — в одной транзакции. Читатель (READ COMMITTED)
  видит либо всё старое, либо всё новое; окна «данные новые, результаты старые»
  нет. Отдельные SELECT одной ручки могут попасть на разные commit — это
  допустимо, следующее SSE-событие заставит фронт перезапросить.
- Удаление — `DELETE`, не `TRUNCATE`: читатели до commit видят старые данные и
  не блокируются.
- `PATCH` сливает и валидирует настройки уже **после** взятия блокировки —
  два параллельных PATCH не теряют друг друга.
- Живое обновление — опрос `risk_summary.version`, не in-process брокер: событие
  не может уйти раньше commit, и всё работает при нескольких воркерах.
- DAO не коммитят; commit делает `crud` в конце единицы работы — иначе
  advisory-lock отпустился бы раньше и атомарность порвалась.

## Интерфейс модуля анализа (`app/analysis/`)

Граница между инфраструктурой и моделью. Пакет — чистый Python, без БД, HTTP и
SQLAlchemy; инфраструктура зависит только от этого контракта. Единственная точка
входа — `app/analysis/__init__.py`:

```python
def default_settings() -> dict                     # настройки по умолчанию, JSON-сериализуемые
def validate_settings(data: dict) -> dict          # нормализует; ошибка -> ValueError("понятный текст")
def analyze(source: SourceData, settings: dict, as_of: datetime) -> AnalysisResult
```

Типы входа и выхода — в `app/analysis/types.py` (`SourceData` из `AccountData` /
`ServiceData` / `TransactionData`; результат — `AnalysisResult` со списком
`CustomerRisk`: `score 0..100 | None`, `level`, `reasons`, `expected_loss_cents`,
произвольный `details`). Сейчас подключена заглушка `app/analysis/stub.py`: всем
клиентам `level="no_data"`, `score=None`, денег нет.

Что инфраструктура гарантирует модели:
- `settings` всегда прошёл `validate_settings`; эффективные настройки —
  `deep_merge(default_settings(), сохранённое)`.
- `as_of` — из ключа `asOf` настроек (ISO-8601), иначе текущий UTC; фактический
  `as_of` пишется в `risk_summary.as_of`.
- `analyze` вызывается в отдельном потоке (`asyncio.to_thread`) — можно считать
  синхронно, цикл событий не блокируется.
- Результат проверяется (`crud.recalc.check_result`): `score` 0..100 или `None`,
  `None` ⇔ `no_data`, `expected_loss_cents ≥ 0`, `account_id` из снимка без
  повторов. Клиент без результата → `no_data`. Нарушение контракта →
  `AnalysisContractError`: транзакция откатывается, ответ `500`, прежние
  результаты целы.

## Как ML-команде подключить модель

1. Реализовать `default_settings`, `validate_settings`, `analyze` в своих модулях
   пакета `app/analysis/` (вместо `stub.py`).
2. Поменять импорт в `app/analysis/__init__.py` на свою реализацию.

Ни база, ни ручки, ни фронт-контракт при этом не меняются.

## Как добавить признак / коэффициент

Признаки, формула score, пороги уровней и денежная оценка живут **только** внутри
`app/analysis/` — это зона ML-команды, здесь их нет.

- Новый коэффициент настроек: добавить ключ в `default_settings()` и учесть его в
  `validate_settings()`. Настройки — это один JSONB (`model_settings.data`),
  поэтому новый ключ появляется без миграции; фронт получает `settings` и
  `defaults` как JSON и сам их не переименовывает.
- Новый признак или причина: считать внутри `analyze`, вернуть в `reasons`
  (пара `code`/`text`) и, при необходимости, в произвольном `details` карточки.
- Новые входные данные о клиенте: при необходимости расширить снимок и типы
  `app/analysis/types.py`, согласовав с инфраструктурой.

## Описание модели (заполняет ML-команда)

> Здесь ML-команда описывает подключённую модель: какие признаки считаются, как
> формируется `score`, пороги уровней `high/medium/low`, смысл и формула
> `expected_loss_cents` и `loss_explanation`, ключи настроек в `default_settings()`.
> Пока подключена заглушка — модель не считает риск.
