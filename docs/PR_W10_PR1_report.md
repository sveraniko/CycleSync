# PR W10 / PR1 — Operational hardening foundation

## 1) Worker/job failure model

Introduced a canonical operational status model for worker-style tasks:

- `queued`
- `running`
- `succeeded`
- `failed`
- `retry_scheduled`
- `dead_letter`

Model is formalized in `app/application/ops/reliability.py` and persisted in `ops.job_runs`.

`ops.job_runs` now stores:

- attempt counters (`attempt_count`, `max_attempts`)
- scheduling (`next_attempt_at`)
- diagnostics (`last_error`)
- terminal state timestamp (`dead_lettered_at`)
- replay metadata (`replayable`, `replayed_from_job_run_id`)

## 2) Retry policy selected

Implemented deterministic bounded retry policy (`RetryPolicy`):

- bounded attempts (`max_attempts`)
- exponential backoff with cap
- deterministic next attempt timestamp (`next_attempt_at`)
- terminal transition to `dead_letter` after retry budget exhaustion

Function: `classify_retry(...)`.

## 3) Dead-letter handling

Dead-letter model is now explicit for both jobs and outbox:

- jobs: `job_runs.status = dead_letter`, `dead_lettered_at`
- outbox: `outbox_events.status = dead_lettered`, `dead_lettered_at`

Operator replay is enabled through scripts/repository APIs:

- replay dead-letter jobs back to `queued`
- replay failed/dead-letter outbox events back to `pending`

## 4) Replay/retry scripts added

Added operator scripts:

- `python scripts/ops_inspect.py`
  - prints operational snapshot (job status counts, outbox counts, lag, failure families)
- `python scripts/ops_retry_dead_letter_jobs.py [limit] [job_name?]`
  - resets replayable dead-letter jobs to queued state
- `python scripts/ops_replay_outbox.py [limit] [aggregate_type?]`
  - requeues outbox events in `failed_retryable` / `dead_lettered`

## 5) Diagnostics additions

`/health/diagnostics` now includes `operational_reliability`:

- failed job counts by type
- retry scheduled count
- dead-letter count
- outbox status distribution
- outbox pending count + retry/dead-letter counts
- outbox lag in seconds
- focused failure counters:
  - reminder dispatch failures
  - lab triage failures
  - checkout fulfillment failures

## 6) Explicitly hardened flows

Hardening foundation now covers operational semantics for:

- reminder dispatch workers
- reminder materialization workers
- lab triage execution jobs (diagnostic family)
- checkout fulfillment jobs (diagnostic family)
- projection rebuild jobs (via generic job model + operational scripts)
- outbox delivery visibility/replay

Also kept idempotency central via existing domain idempotency semantics + explicit replay-focused tests for fulfillment and reminders.

## 7) Exact local verification commands

```bash
pytest tests/test_ops_reliability.py tests/test_commerce_checkout.py tests/test_reminder_materialization.py tests/test_health.py
```

## 8) Canonical baseline migration updated in place

Per baseline policy, **no new migration chain** was created.

Updated directly in:

- `alembic/versions/20260411_0012_baseline_consolidated.py`

Changes done in-place:

- extended `ops.outbox_events` with hardening columns/indexes
- extended `ops.job_runs` with retry/dead-letter/replay columns/indexes

This preserves a single canonical baseline migration.
