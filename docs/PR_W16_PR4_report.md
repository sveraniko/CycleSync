# PR W16 / PR4 — Admin-facing Catalog Sync Surface

## 1) Что сделано: admin catalog sync surface

В админке добавлен новый entrypoint **`📦 Catalog sync`** (admin-only), который открывает отдельную компактную панель операций каталога.  
Панель показывает:
- доступные режимы (validate/dry-run, apply ingest, gsheets sync, search rebuild);
- дефолтный путь workbook (`docs/medical_v2.xlsx`);
- состояние Google Sheets конфигурации;
- блок **Last run** с последним сохранённым результатом операции.

## 2) Added actions

В Catalog sync panel добавлены действия:
- `✅ Validate workbook (dry-run)`  
- `🚀 Run XLSX ingest (apply)`  
- `☁️ Run Google Sheets sync`  
- `🔎 Rebuild search`

Все действия доступны только администраторам; не-админ получает `Нет доступа`.

## 3) Validate vs Apply distinction

Разделение сделано явно в UI и в result summary:
- **validate/dry-run**: проверка workbook без записи в БД;
- **apply**: реальный ingest/sync с записью.

Result summary явно содержит:
- `source`;
- `mode` (`validate` / `apply`);
- `status`;
- `timestamp`;
- `message`;
- счётчики (если доступны).

## 4) Last-run status

Реализован lightweight runtime-state в `AdminRuntimeConfig.last_catalog_operation`:
- source type;
- mode;
- status;
- timestamp;
- message;
- high-level counts.

Состояние эпемерное (до перезапуска бота), что явно соответствует pre-MVP baseline режиму и минимальному practical implementation.

## 5) Missing Google Sheets config behavior

Если Google Sheets не настроен, панель явно показывает `⚠️ Не настроено` с причиной.  
При запуске `Run Google Sheets sync` в таком состоянии возвращается **failed summary**, без silent no-op и без fake success.

## 6) Exact local verification commands

Использованы команды:

```bash
pytest -q tests/test_admin_catalog_sync_smoke.py tests/test_admin_media_upload_policy_smoke.py
pytest -q tests/test_bot_ui_foundation.py
```

## 7) Canonical baseline migration

**Schema changes не потребовались.**  
Canonical baseline migration **не изменялась** в этом PR.
