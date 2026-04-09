# CycleSync Wave 0 / PR2 Report

## Что сделано

### 1) SQLAlchemy baseline conventions
- Введен единый `Base` и общий `MetaData` c `naming_convention` для `pk/fk/ix/uq/ck`.
- Добавлены минимальные миксины:
  - `IDMixin` (`UUID` PK),
  - `TimestampMixin` (`created_at`, `updated_at`),
  - `BaseModel` как общий lightweight-базовый класс.
- Без лишней магии и без глубокого domain-model на этом этапе.

### 2) Alembic подключен
- Добавлены `alembic.ini`, `alembic/env.py`, шаблон миграций и `versions/`.
- `env.py` совместим с async SQLAlchemy runtime: runtime использует async DSN, а Alembic конвертирует драйвер в sync (`+psycopg`) для миграций.
- Автогенерация учитывает схемы (`include_schemas=True`).

### 3) Baseline schemas
В baseline-миграции создаются схемы:
- `compound_catalog`
- `user_registry`
- `protocols`
- `pulse_engine`
- `reminders`
- `adherence`
- `labs`
- `ai_triage`
- `expert_cases`
- `search_read`
- `analytics_raw`
- `analytics_views`
- `ops`

### 4) Ops foundation
Созданы минимальные foundation-таблицы:
- `ops.outbox_events`
- `ops.job_runs`
- `ops.projection_checkpoints`

Это только фундамент для следующего шага (event delivery/projections), без полноценного event bus.

### 5) Readiness и diagnostics
- Readiness проверяет Postgres и Redis с latency/error деталями по каждой зависимости.
- Diagnostics отдает явный JSON с dependency-статусом и агрегированным readiness-флагом.

### 6) Makefile команды для БД
Добавлены команды:
- `make db-upgrade`
- `make db-downgrade`
- `make db-revision MSG="..."`
- `make db-current`
- `make db-reset-local` (dev-only)

### 7) Минимальные smoke-проверки
- Проверка health/diagnostics shape.
- Проверка, что metadata conventions подключены.
- Проверка, что ops модели привязаны к схеме `ops`.

## Добавленные migration files
- `alembic/versions/20260409_0001_baseline_schemas_and_ops.py`

## Что сознательно отложено на следующие PR
- Полная доменная модель (десятки таблиц по bounded contexts).
- Реальная реализация event dispatcher/consumer pipeline.
- Search/read projections и domain-specific truth tables.
- Глубокие бизнес-схемы reminders/labs/protocol execution.
- Отдельные microservices и физическое разделение БД.

## Локальный workflow

### Применить миграции
```bash
make db-upgrade
```

### Создать новую миграцию
```bash
make db-revision MSG="add protocols draft table"
```

### Проверить текущую ревизию
```bash
make db-current
```

### Откатить последнюю миграцию
```bash
make db-downgrade
```

### Полный local reset (dev)
```bash
make db-reset-local
```
