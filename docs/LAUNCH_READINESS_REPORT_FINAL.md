# CycleSync — Launch Readiness Report (Final)

Дата прохода: 2026-04-14 (UTC)
Режим: финальный launch-readiness audit перед локальным live pilot.

## A. Вердикт

**GO WITH RISKS**

Почему не `GO`:
- в текущем runtime нет встроенного scheduler/daemon для reminder materialize+dispatch; без внешнего cron/loop напоминания не «живут» сами по себе;
- в этой среде не удалось поднять Docker-инфру (команда `docker` отсутствует), поэтому end-to-end runtime был верифицирован тестовым smoke-слоем и статическим аудитом, но не full live-процессом с контейнерами.

## B. Blockers

### B1) Reminders не автономны без внешнего расписания
- Подтверждено, что materialize/dispatch реализованы как отдельные скрипты (`scripts/materialize_reminders.py`, `scripts/dispatch_reminders.py`) и не запускаются из `run_bot.py` по таймеру.
- В `docker-compose.yml` нет отдельного scheduler-сервиса.
- Для pilot это блокер в сценарии «подняли бот и забыли»: напоминания без cron/systemd/loop не пойдут автоматически.

### B2) Невозможность проверить live startup в текущем окружении
- `docker compose up -d postgres redis meilisearch` не выполнен: `docker: command not found`.
- `alembic upgrade head` не выполнился из-за недоступного host `postgres` (ожидаемо без поднятого compose).

> Это инфраструктурный блокер среды проверки, не кодовый дефект репозитория.

## C. Risks (не блокируют старт, но важны для pilot)

1. **Тестовый долг на copy/UX smoke**: часть smoke-тестов падает из-за устаревших ожиданий старых EN-строк и старых label’ов, а не из-за functional logic.
2. **Bot live startup требует реальный `BOT_TOKEN`**: без токена `run_bot.py` завершится с `RuntimeError`.
3. **Google Sheets sync зависит от конфигурации**: без `GOOGLE_SHEETS_*` админ-панель корректно покажет fail-состояние (ожидаемое поведение), но оператор должен понимать, что primary path для pilot — XLSX V2.
4. **Reminder dispatch path зависит от Telegram API доступности** (и валидного токена), иначе будут failed deliveries.

## D. Exact launch steps (локальный pilot)

1. **Подготовить env**
   - `cp .env.example .env`
   - заполнить минимум:
     - `BOT_TOKEN=<real token>`
     - `BOT_ADMIN_IDS=<your_telegram_id>`
     - при необходимости `MEILISEARCH_API_KEY`.

2. **Поднять инфраструктуру**
   - `docker compose up --build -d`

3. **Проверить connectivity**
   - `python -m scripts.check_connectivity`
   - ожидание: postgres/redis/meilisearch = ok.

4. **Поднять БД baseline**
   - `alembic upgrade head`
   - проверить, что используется единый baseline (`20260411_0012_baseline_consolidated.py`).

5. **Catalog V2 validate/apply**
   - validate: через admin panel `📦 Catalog sync -> ✅ Validate workbook (dry-run)`
     или сервисно через `CatalogAdminSyncService.validate_workbook()` (default path `docs/medical_v2.xlsx`).
   - apply: `📦 Catalog sync -> 🚀 Run XLSX ingest (apply)`.

6. **Search rebuild**
   - `python -m scripts.rebuild_search_projection`
   - либо admin panel: `🔎 Rebuild search`.

7. **Запустить API + Bot**
   - API: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
   - Bot: `python -m app.run_bot`

8. **Runtime/admin checks**
   - в админке проверить runtime panel (commerce/debug toggles);
   - проверить `Catalog sync` last-run summary;
   - проверить media/source policy controls на карточке.

9. **First smoke**
   - пройти чеклист из раздела E.

## E. Pilot smoke checklist (кликабельный маршрут)

1. **Search**
   - найти по trade name;
   - найти по ingredient/ester;
   - проверить alias/RU/EN/translit кейсы.
2. **Card**
   - открыть карточку;
   - проверить Official button;
   - проверить Source buttons (мульти-source);
   - проверить media toggle + cover behavior.
3. **Draft/Calculation**
   - `+Draft` -> открыть Draft;
   - wizard -> preview -> pre-start -> activation;
   - active protocol -> estimator.
4. **PK V2 path**
   - убедиться, что в summary отображается `pulse_engine_version_used=v2`;
   - проверить, что mixed products не ломают preview/activation.
5. **Labs/Triage/Specialist**
   - Labs root -> New report -> marker entry -> AI triage -> specialist case.
6. **Commerce/Access**
   - Activate key flow;
   - checkout demo entrypoint при `commerce_enabled=ON`;
   - debug actions видны только admin при `debug_enabled=ON`.
7. **Admin media/source/sync**
   - policy mode (`import_only/manual_only/prefer_manual/merge`);
   - display mode (`none/on_demand/show_cover_on_open`);
   - sync toggles (`images/videos/sources`) и видимый эффект в карточке.

## F. Reminder runbook (что нужно, чтобы reminders реально жили локально)

Минимально рабочая схема для pilot:

1. После активации протокола периодически запускать materialization:
   - `python -m scripts.materialize_reminders 100`
2. Периодически запускать dispatch:
   - `python -m scripts.dispatch_reminders`
3. Частота для pilot:
   - materialize: каждые 1-5 минут;
   - dispatch: каждые 1 минуту.
4. Реализация расписания (любой один вариант):
   - cron;
   - systemd timer;
   - supervisor loop;
   - отдельный scheduler container.

**Важно:** без внешнего scheduler reminders не являются self-sustained runtime.

## G. If fixes were made

Кодовые launch-fixes в этом проходе **не вносились**: giant/refactor изменений не требовалось для фиксации найденной картины; подготовлены только финальный отчёт и короткий pilot runbook.

## Что подтверждено в рамках прохода

- Canonical baseline один: `alembic/versions/20260411_0012_baseline_consolidated.py`.
- V2 workbook canonical path: `docs/medical_v2.xlsx`.
- PK V2 default path подтвержден через config+selector (`pulse_engine_version` default `v2`, fallback в `resolve_pulse_engine_version`).
- Admin catalog sync surface и validate/apply distinction подтверждены тестами.
- Media/source policy + display mode + sync toggle surfaces подтверждены тестами.
- Core protocol/labs/checkout/access/reminder materialization path покрыт smoke/functional тестами (см. список внизу этого прохода).

## Артефакты тестового прохода (локально)

### Успешный целевой smoke
- `pytest -q tests/test_db_baseline.py tests/test_catalog_v2_ingest_foundation.py tests/test_medical_v2_validation_pack.py tests/test_catalog_ingest_idempotent.py tests/test_search_projection.py tests/test_search_service.py tests/test_medical_catalog_search_regression.py tests/test_admin_media_upload_policy_smoke.py tests/test_pk_v2_foundation.py tests/test_protocol_activation.py tests/test_course_estimator.py tests/test_bot_labs_smoke.py tests/test_bot_specialist_flow_smoke.py tests/test_bot_checkout_smoke.py tests/test_bot_access_key_smoke.py tests/test_reminder_materialization.py tests/test_adherence_intelligence.py`
  - результат: **91 passed**.

### Отдельно зафиксированные проблемы
- `docker compose up -d postgres redis meilisearch` -> `docker: command not found`.
- `alembic upgrade head` -> connection error к host `postgres` (без поднятой infra).
- Расширенный smoke-пакет с частью UI-copy тестов выявил 11 падений ожиданий старых label/text (не functional-runtime).
