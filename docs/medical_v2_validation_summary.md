# Medical V2 Validation Summary

Generated at: `2026-04-13T22:54:12.892395+00:00`

## Scenarios with no material difference

- `PKV2-I1`

## Scenarios where V2 changed flatness significantly (|delta| >= 5)

- `PKV2-A1`: delta `-57.20`
- `PKV2-S1`: delta `-57.31`
- `PKV2-T1`: delta `-52.06`
- `PKV2-M1`: delta `-57.23`

## Scenarios where V2 emitted new warnings

- `PKV2-A1`: +flatness_below_target, peak_trough_spread_high
- `PKV2-S1`: +flatness_below_target, peak_trough_spread_high
- `PKV2-T1`: +flatness_below_target, peak_trough_spread_high
- `PKV2-M1`: +flatness_below_target, mixed_ester_short_component_spikes, peak_trough_spread_high

## Mixed products most affected by V2

- `PKV2-S1`: flatness delta `-57.31`, strictness `more_strict`, schedule_same_eval_changed=`True`
- `PKV2-T1`: flatness delta `-52.06`, strictness `same`, schedule_same_eval_changed=`True`
- `PKV2-I1`: flatness delta `0.00`, strictness `same`, schedule_same_eval_changed=`False`
- `PKV2-M1`: flatness delta `-57.23`, strictness `more_strict`, schedule_same_eval_changed=`True`

## Search regression

- Matched cases: `8/11`
