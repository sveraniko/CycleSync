# PR_W2_PR2 — Pulse Engine MVP + Preview Truth

## Что реализовано

### 1) Deterministic pulse calculation core

Добавлен MVP-движок `PulseCalculationEngine` с тремя preset-стратегиями:
- `unified_rhythm`
- `layered_pulse`
- `golden_pulse`

Важные свойства:
- deterministic (одни и те же input → тот же output);
- transparent heuristics (half-life driven intervals, volume/mg math, phase offsets);
- без black-box «AI calculation».

### 2) Fallback behavior

Для `golden_pulse` реализован честный деградационный путь:
- если кейс слишком сложный/ограниченный для MVP,
- стратегия явно fallback в `layered_pulse`,
- статус расчета = `degraded_fallback`,
- warning flag = `golden_pulse_fallback_to_layered`.

### 3) Preview persistence model (`pulse_engine` schema)

Добавлены таблицы preview truth:
- `pulse_engine.pulse_calculation_runs`
- `pulse_engine.pulse_plan_previews`
- `pulse_engine.pulse_plan_preview_entries`

Каждый preview фиксирует:
- source draft;
- settings snapshot;
- requested/applied preset;
- calculation status;
- summary metrics;
- warning/degraded flags;
- generated schedule entries.

### 4) Status model

Engine возвращает только явные outcome классы:
- `success`
- `success_with_warnings`
- `degraded_fallback`
- `failed_validation`

### 5) Summary metrics

В preview сохраняются минимум:
- `flatness_stability_score`
- `estimated_injections_per_week`
- `max_volume_per_event_ml`
- `warning_flags`
- `degraded_fallback`

### 6) Schedule entry model

Каждая planned entry содержит:
- `day_offset` / optional `scheduled_day`
- `product_id`
- `ingredient_context`
- `volume_ml`
- `computed_mg`
- `injection_event_key`
- `sequence_no`

### 7) Bot UX seam (PR2)

После readiness flow пользователь может:
- запустить расчет preview;
- получить compact summary + warnings + первые schedule lines;
- пересчитать preview;
- сменить preset;
- видеть activation как seam (без реальной активации в PR2).

### 8) Events / outbox hooks

Добавлены hooks:
- `pulse_calculation_started`
- `pulse_plan_preview_generated`
- `pulse_plan_preview_failed`
- `pulse_plan_preview_regenerated`

## Что НЕ делалось в PR2 (осознанно)

- permanent protocol activation;
- reminder rows/dispatch;
- labs/expert/commercial контуры;
- ручной low-level editor распределения доз.

## Что остается на PR3

- explicit protocol confirmation/activation lifecycle;
- binding active protocol к выбранному preview;
- downstream generation of reminder truth from active pulse plan;
- stricter recalculation/supersession rules for active protocols;
- расширение UX around activation and execution handoff.
