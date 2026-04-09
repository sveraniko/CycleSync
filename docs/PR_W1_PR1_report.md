# PR W1 / PR1 — Compound Catalog Transactional Foundation

## Что сделано

### Введенные catalog entities
- `compound_catalog.brands`
- `compound_catalog.compound_products`
- `compound_catalog.compound_aliases`
- `compound_catalog.compound_ingredients`
- `compound_catalog.product_media_refs`
- `compound_catalog.catalog_ingest_runs`
- `compound_catalog.catalog_source_records`

Все сущности имеют стабильные внутренние UUID, `created_at` / `updated_at`, и (где применимо) `is_active`.

### Принятая ingest схема
- Источник: Google Sheets (read-only), через отдельный gateway адаптер.
- Поток ingest:
  1. fetch rows,
  2. normalization,
  3. validation + mapping,
  4. upsert transactional catalog truth,
  5. run-level + row-level trace (`catalog_ingest_runs`, `catalog_source_records`).
- Поведение idempotent/promotion-based:
  - продукт идентифицируется по stable key (`brand + normalized_trade_name + release_form + concentration_raw`),
  - повторный ingest тех же данных обновляет существующую запись, а не создает дубликаты,
  - aliases/ingredients/media поддерживаются через controlled replace внутри транзакционного обновления.

### Operational entrypoint
- Добавлен ручной запуск ingest: `python scripts/run_catalog_ingest.py`.
- Сервис не пишет обратно в Google Sheets.

### Readiness / diagnostics
- В diagnostics добавлен `catalog_source` блок с флагом конфигурации.
- Отсутствие Google Sheets конфигурации не ломает readiness приложения.

## Что сознательно НЕ сделано в этом PR
- Нет Meilisearch integration.
- Нет user-facing browse/catalog UX.
- Нет Telegram search UX.
- Нет draft/protocol UX изменений.
- Нет pulse/reminders/adherence/labs/expert/commercial логики.

## Что планируется в PR2
- Search projection слой для catalog truth.
- Синхронизация каталога в Meilisearch.
- Search ranking/tuning и retrieval contracts.
- User-facing search-first UX поверх projection.

## Локальный запуск ingest
1. Заполнить env-переменные:
   - `CATALOG_INGEST_ENABLED=true`
   - `GOOGLE_SHEETS_SHEET_ID=...`
   - `GOOGLE_SHEETS_TAB_NAME=Catalog`
   - и service account (`GOOGLE_SHEETS_CREDENTIALS_PATH` или `GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON`, если включен `GOOGLE_SHEETS_USE_SERVICE_ACCOUNT=true`).
2. Применить миграции: `alembic upgrade head`.
3. Запустить ingest: `python scripts/run_catalog_ingest.py`.
