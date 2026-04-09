# CycleSync Wave 0 / PR1 Report

## Что сделано
- Собран foundation skeleton c разделением на `api`, `bots`, `application`, `domain`, `infrastructure`, `workers`, `core`.
- Добавлен typed config через `pydantic-settings` (`Settings`) + `.env.example`.
- Добавлен bootstrap structured logging на `structlog` в JSON-формате.
- Поднят FastAPI shell с lifespan и health endpoints:
  - `/health/live`
  - `/health/ready`
  - `/health/diagnostics`
- Добавлен bootstrap инфраструктуры:
  - async SQLAlchemy engine/session factory
  - Redis asyncio client
  - ping-level readiness checks
  - корректное закрытие ресурсов на shutdown
- Добавлен aiogram bot shell (`app/run_bot.py`) с минимальным `/start` handler.
- Добавлены runtime-артефакты:
  - `Dockerfile`
  - `docker-compose.yml` (api, bot, postgres, redis)
  - `Makefile` targets (`up`, `down`, `logs`, `api`, `bot`, `format`, `lint`, `test`)
- Добавлены минимальные smoke tests (`tests/test_health.py`).

## Что сознательно НЕ делалось
- Не реализованы domain-specific сценарии CycleSync.
- Не добавлены OCR, Meilisearch, Google Sheets, pulse engine, reminders business logic, labs, specialist flow.
- Не добавлены domain tables и миграции Alembic baseline (перенесено в PR2).
- Не добавлены search/protocol flows.

## Entrypoints
- API (локально): `make api`
- Bot (локально): `make bot`
- Compose runtime: `make up`
- Connectivity check script: `python scripts/check_connectivity.py`

## Обязательные env vars
Минимально для полного runtime:
- `BOT_TOKEN`
- `POSTGRES_DSN`
- `REDIS_DSN`

Рекомендуемые:
- `APP_ENV`
- `LOG_LEVEL`
- `API_HOST`
- `API_PORT`
- `TIMEZONE_DEFAULT`

## Ожидаемые шаги в PR2
- Подключить Alembic baseline и первую миграцию.
- Завести базовые domain tables и metadata.
- Добавить db session dependency в API dependency graph.
- Уточнить readiness semantics (например, явные reason-коды и timeout policy).
- Добавить CI checks (lint/test) и pre-commit hooks.
