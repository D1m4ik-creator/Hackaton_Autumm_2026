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
  analysis/    контракт модели риска и адаптер churn.py (чистый Python, без БД и HTTP)
  ml/          логистическая модель оттока churn_model.py (только стандартная библиотека)
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
произвольный `details`). Подключена логистическая модель оттока: адаптер
`app/analysis/churn.py` готовит снимок клиента для `app/ml/churn_model.py`,
переводит вероятность в `score`/`level` и считает денежную оценку (см. раздел
[«Описание модели»](#описание-модели)).

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

## Как подключена модель

Логистическая модель живёт в `app/ml/churn_model.py`, адаптер к контракту
`app/analysis/` — в `app/analysis/churn.py`; импорт в `app/analysis/__init__.py`
указывает на адаптер. Менять модель или веса можно, не трогая базу, ручки и
фронт-контракт.

## Как добавить признак / коэффициент

Признаки, формула score, пороги уровней и денежная оценка живут **только** внутри
`app/analysis/` и `app/ml/` — это зона модели.

- Новый коэффициент настроек: добавить ключ в `default_settings()` и учесть его в
  `validate_settings()` (`app/analysis/churn.py`). Настройки — это один JSONB
  (`model_settings.data`), поэтому новый ключ появляется без миграции; фронт
  получает `settings` и `defaults` как JSON и сам их не переименовывает.
- Новый признак: вычислить его в `extract_features` (`app/ml/churn_model.py`,
  значение в `[0, 1]`) и добавить вес в `weights` — через `default_settings()`
  или через сохранённые настройки (`PATCH /model/settings`). Вес без реализации
  признака даёт нулевой вклад (модель берёт `features.get(name, 0.0)`), поэтому
  коэффициент можно завести заранее. Текст причины — в `_REASON_TEXTS`
  (`app/analysis/churn.py`); для неизвестного имени показывается «Признак «имя»».
- Новые входные данные о клиенте: при необходимости расширить снимок и типы
  `app/analysis/types.py`, согласовав с инфраструктурой.

## Описание модели

Исторических данных для обучения нет, поэтому риск оттока оценивается
логистической моделью с экспертно заданными весами (weighted scoring):

```
logit = bias + Σ weightᵢ · featureᵢ
probability = sigmoid(logit)
```

Все признаки приведены к диапазону `[0, 1]` (бинарные или доли), поэтому веса
напрямую сравнимы между собой.

### Признаки и веса по умолчанию

Веса — экспертная оценка в шкале логита (`ModelConfig.weights`):

| Признак | Вес | Смысл |
|---|---|---|
| `has_prolong_wait` | +3.0 | Есть услуга «Ожидает оплаты» — сильнейший сигнал |
| `prolong_wait_without_funds` | +2.0 | Ждёт оплаты, а доступных денег не хватает |
| `failed_payment_ratio` | +2.0·доля | Доля неуспешных платежей |
| `balance_deficit` | +1.5 | Ближайших продлений не хватает средств |
| `autoprolong_off_ratio` | +1.5·доля | У активных услуг выключено автопродление |
| `expires_soon_no_autoprolong` | +1.2 | Услуга скоро истекает без автопродления |
| `suspended_ratio` | +1.0·доля | Доля приостановленных услуг |
| `deleted_blocked_ratio` | +1.0·доля | Доля удалённых/заблокированных (история) |
| `full_autoprolong_coverage` | −1.0 | Всё продлевается автоматически (защитный) |
| `sufficient_funds` | −0.8 | Средств хватает на продления (защитный) |

`bias = −2.5` по умолчанию: клиент без тревожных сигналов считается лояльным.
`deleted`/`blocked` — свершившийся факт, они дают только исторический признак
`deleted_blocked_ratio`, но не сигналы будущего оттока. Доступные средства —
баланс плюс бонусы, но бонусы учитываются только при `bonusState = "unlocked"`;
реферальный `withdrawBalance` не учитывается.

### score и уровни

`score = round(probability · 100)`, ограничен `0..100`. Уровень по порогам
`thresholds` (по score):

- `score ≥ thresholds.high` (70) → `high`;
- `score ≥ thresholds.medium` (35) → `medium`;
- иначе → `low`.

Если у клиента нет ни услуг, ни транзакций — `level = "no_data"`, `score = None`,
причина «Недостаточно данных для оценки», потери 0.

`reasons` — положительные вклады признаков (`weight · value > 0`) по убыванию,
максимум три; `code` — имя признака, текст — из словаря причин. Если
положительных вкладов нет — «Тревожных сигналов не найдено».

### Денежная оценка потерь

`expected_loss_cents` за горизонт `horizonDays` (дней):

```
loss = probability · Σ (priceₛ · paymentsₛ)   по «живым» услугам
paymentsₛ = max(1, floor(horizonDays / дней_в_периодеₛ))
```

«Живые» услуги — `active`, `prolong_wait`, `suspended` (`deleted`/`blocked` не
считаются). Длительность периода в днях: `hour` 1/24, `week` 7, `month` 30,
`quarter_year` 91, `half_year` 182, `year` 365; неизвестный период — одна оплата
за горизонт. Итог округляется до целых евроцентов (`≥ 0`). Смысл суммы панели
объясняет `loss_explanation`.

### Настройки (`default_settings()`)

| Ключ | По умолчанию | Назначение |
|---|---|---|
| `asOf` | `null` | Момент оценки (ISO-8601) или `null` → текущий UTC |
| `weights` | из `ModelConfig` | Веса признаков; допускаются новые имена |
| `bias` | `−2.5` | Свободный член логита |
| `threshold` | `0.5` | Порог классификации модели (на score не влияет) |
| `thresholds` | `{high: 70, medium: 35}` | Пороги уровней по score |
| `expiresSoonDays` | `7` | Окно «скоро истекает» (1..365) |
| `horizonDays` | `30` | Горизонт денежной оценки (1..3650) |

`validate_settings` проверяет типы и диапазоны (веса и `bias` — конечные числа,
не bool; `0 ≤ medium < high ≤ 100`), допускает дополнительные имена весов и
сохраняет неизвестные ключи верхнего уровня; при ошибке — `ValueError` с
понятным русским текстом. `details` каждого клиента содержит `probability`,
`features`, `contributions`, `bias`, `liveServices`, `horizonDays`.
