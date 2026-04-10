# PR W3 / PR1 — Pulse Calculation Core Hardening

## Что изменено в allocation logic

В этом PR allocation в `PulseCalculationEngine` перестроен с naive equal-split на детерминированную pharmacology-aware схему:

1. `guidance_weighted`: если по всем выбранным продуктам есть `dose_guidance_typical_mg_week`, распределение weekly target идет по суммарным typical guidance.
2. `guidance_range_weighted`: если typical есть не везде, используются typical + midpoint от `dose_guidance_min/max_mg_week`.
3. `driver_biased`: если guidance недостаточно, применяются `is_pulse_driver` + half-life контекст (короткий half-life и драйвер получают больший вес).
4. `equal_fallback`: только крайний fallback, когда metadata практически отсутствует.

Allocation теперь возвращает объяснимые детали (`allocation_details`) и per-product weekly target, а не скрытую эвристику.

## Allocation modes

Поддерживаемые режимы:

- `guidance_weighted`
- `guidance_range_weighted`
- `driver_biased`
- `equal_fallback`

Режим сохраняется в summary и persistence, чтобы аналитика и debug могли видеть, как именно был получен preview.

## Guidance coverage score

Введен `guidance_coverage_score` (0..100), учитывающий:

- coverage по usable dose guidance,
- coverage по usable half-life,
- penalty при `equal_fallback`.

Это делает видимой качество входных pharmacology данных для расчета.

## Quality flags

Добавлены расчетные quality/warning flags:

- `dose_guidance_missing_for_some_products`
- `allocation_used_equal_fallback`
- `pulse_driver_missing`
- `half_life_conflict_detected`

Флаги попадают в summary, warning output и persistence snapshots.

## Preview event semantics cleanup

Исправлена семантика lifecycle событий preview:

- первый успешный preview для draft lineage: `pulse_plan_preview_generated`
- последующие успешные preview: `pulse_plan_preview_regenerated`
- неуспешный preview: только `pulse_plan_preview_failed`

Убран анти-паттерн, когда один успешный preview эмитил одновременно `generated` и `regenerated`.

## Persistence updates

В `pulse_calculation_runs` и `pulse_plan_previews` добавлены поля:

- `allocation_mode`
- `guidance_coverage_score`
- `calculation_quality_flags_json`
- `allocation_details_json`

Это обеспечивает traceability и foundation для execution-layer PR без внедрения reminders/adherence runtime.

## Что остается на следующий PR

- execution-layer orchestration поверх уже explainable pulse core;
- reminder scheduling runtime и delivery policy (отдельным контролируемым PR);
- adherence state transitions и post-execution feedback loop (отдельно);
- дополнительные projection/read-model оптимизации под execution timeline.
