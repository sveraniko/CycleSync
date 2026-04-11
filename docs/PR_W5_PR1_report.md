# PR W5 / PR1 — Adherence intelligence layer

## 1) Introduced adherence summary model

Added a dedicated projection table `adherence.protocol_adherence_summaries` (derived from `adherence.protocol_adherence_events` truth):

- `protocol_id`
- `pulse_plan_id`
- `user_id`
- `completed_count`
- `skipped_count`
- `snoozed_count`
- `expired_count`
- `total_actionable_count`
- `completion_rate`
- `skip_rate`
- `expiry_rate`
- `last_action_at`
- `integrity_state`
- `integrity_reason_code`
- `broken_reason_code`
- `integrity_detail_json`
- `updated_at`

Also added optional protocol flags:
- `protocols.protocols.protocol_integrity_flagged_at`
- `protocols.protocols.protocol_broken_at`

## 2) Integrity states

Deterministic integrity states:

- `healthy`
- `watch`
- `degraded`
- `broken`

## 3) Deterministic classification rules

Implemented explicit rules in `app/application/reminders/adherence.py`:

Broken (highest priority):
- `consecutive_expiries` — 3+ consecutive `expired`.
- `consecutive_negative_events` — 4+ consecutive negative (`skip`/`expired`).
- `high_expiry_rate` — expiry rate >= 50% with actionable >= 4.
- `low_completion_ratio` — completion rate < 40% with actionable >= 6.

Degraded:
- `mixed_noncompliance_pattern` — 3+ consecutive negative events.
- `high_skip_rate` — skip rate >= 50% with actionable >= 4.
- `elevated_expiry_rate` — expiry rate >= 34% with actionable >= 3.
- `low_completion_ratio` — completion rate < 60% with actionable >= 5.

Watch:
- `recent_misses` — 2 consecutive negative events.
- `rising_skip_rate` — skip rate >= 30% with actionable >= 4.
- `soft_completion_drop` — completion rate < 75% with actionable >= 4.
- `high_snooze_volume` — snooze count >= 3 (weak signal only).

Healthy:
- no watch/degraded/broken triggers.

Important rule: `snooze` is a weak signal and does not hard-break protocol integrity.

## 4) Reason codes

Added explainable reason codes:

- `consecutive_expiries`
- `consecutive_negative_events`
- `high_expiry_rate`
- `high_skip_rate`
- `low_completion_ratio`
- `mixed_noncompliance_pattern`
- `elevated_expiry_rate`
- `recent_misses`
- `rising_skip_rate`
- `soft_completion_drop`
- `high_snooze_volume`

## 5) Summary refresh / rebuild path

Refresh path is deterministic and idempotent:

- On each write into `protocol_adherence_events`, repository rebuilds protocol summary from truth events.
- Integrity classification is recalculated from aggregated counts + recent event sequence.
- Projection row is upserted in `protocol_adherence_summaries`.
- Outbox events emitted:
  - `protocol_integrity_updated`
  - `protocol_degraded` (on transition)
  - `protocol_broken` (on transition)
  - `protocol_integrity_recovered` (on recovery to healthy)

Rebuild path:

- `ReminderApplicationService.rebuild_protocol_adherence_summary(protocol_id)` delegates to repository rebuild from truth.

## 6) User and operator visibility

User-facing:
- Added `Protocol status` action in bot settings.
- User sees concise adherence state, completion rate, misses, and reason code.

Operator/diagnostics:
- Extended diagnostics with:
  - `integrity_state_counts`
  - `broken_protocol_count`
  - `degraded_protocol_count`
  - `top_integrity_reason_codes`

## 7) What is intentionally NOT included

- No labs/AI/specialist logic.
- No automatic protocol suspension/deactivation enforcement.
- No giant dashboard implementation.
- No heavy reminder runtime refactor.

## 8) Local verification commands

```bash
pytest tests/test_adherence_intelligence.py tests/test_bot_settings_smoke.py tests/test_reminder_materialization.py tests/test_health.py
```
