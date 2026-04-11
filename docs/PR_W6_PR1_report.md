# PR W6 / PR1 — Labs Foundation (manual structured input first)

## 1) Введенные labs entities

Добавлены transactional сущности в `labs` schema:

- `labs.markers`
- `labs.marker_aliases`
- `labs.lab_panels`
- `labs.lab_panel_markers`
- `labs.lab_reports`
- `labs.lab_report_entries`

ORM-модели реализованы в `app/domain/models/labs.py`.

## 2) Marker library

Реализована canonical marker library с полями:

- `marker_code`
- `display_name`
- `category_code`
- `default_unit`
- `accepted_units` (array)
- `notes`
- `is_active`

В baseline добавлен seed MVP-маркеров (male_hormones, hematology, lipids, liver, metabolic, gh_related).

## 3) Internal panels

Поддержаны внутренние panel shortcuts:

- `male_hormones`
- `hematology`
- `lipids`
- `liver`
- `metabolic`
- `gh_related`

Связка панелей и маркеров хранится в `labs.lab_panel_markers`.

## 4) Manual entry flow (bot)

Реализован structured flow в `app/bots/handlers/labs.py`:

1. user открывает `Labs`
2. `New report`
3. ввод даты отчета
4. ввод / skip источника лаборатории
5. выбор panel
6. marker-by-marker ввод:
   - value
   - unit
   - optional reference min/max
7. skip marker / finish panel
8. finalize report
9. `History` показывает список отчетов

## 5) Validations

Реализованы в `LabsApplicationService`:

- marker existence check
- unit acceptance check against marker accepted units
- numeric parse for entered value
- reference range validation (`min <= max`)
- structured entry only (no OCR blob path)

## 6) Events

Добавлены/используются события:

- `lab_report_created`
- `lab_result_entry_added`
- `lab_result_entry_updated`
- `lab_report_finalized`
- `lab_panel_started`
- `lab_panel_completed`

События пишутся в outbox через `ops.outbox_events`.

## 7) Что сознательно НЕ делалось

- OCR-first parsing
- AI triage
- specialist case assembly
- charts/trends dashboards
- automatic unsafe unit conversions

## 8) Baseline migration policy

Схема обновлена **в текущей canonical baseline migration in place**:

- файл: `alembic/versions/20260411_0012_baseline_consolidated.py`
- новая цепочка миграций **не создавалась**

## 9) Exact local verification commands

```bash
pytest tests/test_db_baseline.py tests/test_labs_service.py tests/test_bot_labs_smoke.py
pytest
```
