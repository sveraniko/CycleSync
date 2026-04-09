# PR_W2_PR1 — Pulse Preparation Foundation

## Что реализовано

Wave 2 / PR1 подготавливает foundation для будущего pulse engine, не реализуя саму pulse-математику.

### 1) Catalog pharmacology metadata

Добавлены поля в transactional truth (`compound_catalog`) для расчетной пригодности.

**Ingredient-level (`compound_ingredients`):**
- `half_life_days`
- `dose_guidance_min_mg_week`
- `dose_guidance_max_mg_week`
- `dose_guidance_typical_mg_week`
- `is_pulse_driver`

**Product-level (`compound_products`):**
- `max_injection_volume_ml`
- `is_automatable`
- `pharmacology_notes`
- `composition_basis_notes`

### 2) Ingest: schema / mapping / normalization / upsert

Обновлены ingest-модели и mapping Google Sheets:
- top-level колонки продукта парсятся в новый pharmacology payload;
- ingredient token расширен до 10-компонентного формата:
  `name|qualifier|amount|unit|basis|half_life_days|dose_min|dose_max|dose_typical|is_pulse_driver`;
- добавлен boolean parser (`yes/no`, `true/false`, `да/нет`, `1/0`);
- upsert логика пишет новые поля в `compound_products` и `compound_ingredients`;
- idempotent поведение сохранено.

### 3) Protocol calculation input contract

Добавлен отдельный слой настроек расчета:
- таблица `protocols.protocol_draft_settings`;
- сервисные DTO `DraftSettingsInput` / `DraftSettingsView`;
- репозиторные методы upsert/get settings.

**Поля контракта:**
- `draft_id`
- `weekly_target_total_mg`
- `duration_weeks`
- `preset_code`
- `max_injection_volume_ml`
- `max_injections_per_week`
- `planned_start_date`
- `updated_at` (через базовый timestamp)

### 4) Readiness validation

Реализован `ProtocolDraftReadinessService`:
- проверяет готовность draft к расчету;
- возвращает structured результат `DraftReadinessResult` + список `DraftReadinessIssue`;
- валидирует обязательные input settings;
- выявляет catalog gaps:
  - non-automatable products,
  - отсутствие `half_life` у ингредиентов;
- выявляет ограничения с конфликтным/подозрительным профилем (warning по высоким injection frequency).

### 5) Bot flow: `К расчету`

Stub заменен на guided protocol-preparation flow:
1. ввод `weekly_target_total_mg`;
2. ввод `duration_weeks`;
3. выбор preset:
   - `Unified Rhythm`
   - `Layered Pulse`
   - `Golden Pulse / Conveyor`
4. ввод `max_injection_volume_ml`;
5. ввод `max_injections_per_week`;
6. выдача readiness summary.

Flow следует правилам:
- нет ручного распределения mg по продуктам;
- язык protocol preparation, не shopping cart;
- короткий guided path без бесконечного мастера.

## Expected sheet columns (PR1)

### Product columns
- `max_injection_volume_ml`
- `is_automatable`
- `pharmacology_notes`
- `composition_basis_notes`

### Ingredient serialization
Поле `ingredients` поддерживает расширенный token формат:
- `name|qualifier|amount|unit|basis|half_life_days|dose_min|dose_max|dose_typical|is_pulse_driver`

> Backward compatibility: старый 5-польный формат токена продолжает работать (новые поля остаются `NULL`).

## Что готово для PR2

После PR1 система готова к внедрению pulse calculation engine:
- pharmacology metadata доступна в catalog truth;
- расчетный input contract формализован и сохранен вне message-state;
- readiness gate присутствует и структурирован;
- bot собирает параметры, валидирует и отдает диагностический summary.

## Что intentionally НЕ реализовано в PR1

- pulse math / optimization / schedule generation;
- создание pulse plan таблиц и calendar lines;
- protocol activation;
- reminders;
- labs / expert / commercial контуры;
- ручной scheme editor (manual per-compound mg distribution).
