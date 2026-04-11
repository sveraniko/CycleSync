# PR W4 / PR2 Report — Reminder Runtime Execution

## 1) Added runtime fields / tables

### `reminders.protocol_reminders` (runtime extension)
- `sent_at`
- `delivery_attempt_count`
- `last_delivery_error`
- `last_message_chat_id`
- `last_message_id`
- `awaiting_action_until_utc`
- `snoozed_until_utc`
- `acted_at`
- `action_code`
- `clean_after_utc`
- index: `ix_protocol_reminders_status_snooze(status, snoozed_until_utc)`

### `adherence.protocol_adherence_events`
- truth table for minimal adherence execution facts
- core fields:
  - `protocol_id`
  - `pulse_plan_id`
  - `reminder_id`
  - `user_id`
  - `action_code`
  - `occurred_at`
  - `payload_json`

## 2) Due selection behavior

Implemented in repository `claim_due_reminders(now_utc, limit)` with deterministic ordering:
- eligible:
  - `status = scheduled AND scheduled_at_utc <= now`
  - `status = snoozed AND snoozed_until_utc <= now`
- excluded implicitly by state filters:
  - `suppressed`, `completed`, `skipped`, `expired`, `cancelled`, `cleaned`
- repeat-safe worker claim:
  - `FOR UPDATE SKIP LOCKED`
  - claimed rows are moved to `delivery_in_progress`

## 3) Implemented state-machine subset

Implemented runtime transitions:
- `scheduled|snoozed -> delivery_in_progress -> awaiting_action` (successful send)
- `delivery_in_progress -> failed_delivery` (send failure)
- `awaiting_action -> completed` (`Done`)
- `awaiting_action -> snoozed` (`Snooze`)
- `awaiting_action -> skipped` (`Skip`)
- `awaiting_action -> expired` (no response until `awaiting_action_until_utc`)
- terminal/chat-hygiene transition:
  - `completed|skipped|expired|snoozed -> cleaned` after Telegram message cleanup

## 4) Delivery / callback / cleanup flow

### Delivery worker path
Entrypoint:
- `python -m scripts.dispatch_reminders`
- `make reminders-dispatch`

Flow:
1. claim due reminders
2. render reminder text with context (event key, product, mg, ml)
3. send Telegram message with inline buttons `Done / Snooze / Skip`
4. persist delivery metadata (`chat_id`, `message_id`, attempts, sent timestamps)
5. move reminder to `awaiting_action`
6. run expiry sweep and clean stale UI for expired reminders

### Callback path
Handler: `app/bots/handlers/reminder_actions.py`
- parses callback `reminder:{reminder_id}:{done|snooze|skip}`
- applies idempotent-aware action transition
- writes adherence event (`done|snooze|skip`) once
- cleans stale actionable message by editing and removing buttons

### Cleanup strategy
- no stale actionable cards after terminal/action transitions
- worker also cleans on expiry
- cleanup uses Telegram message edit (set resolved/non-actionable text + remove keyboard)

## 5) Adherence truth write path

Truth persistence is explicit via repository method `record_adherence_event(...)` and table `adherence.protocol_adherence_events`.

Recorded actions in this PR:
- `done`
- `snooze`
- `skip`
- `expired`

This is raw truth capture only; scoring/broken-protocol automation intentionally deferred.

## 6) Intentional limitations left for next PR

- no broken-protocol automation/escalation machine
- no adherence scoring/aggregation model
- no multi-step retry chains beyond a single failed-delivery terminal state
- no cross-channel delivery platform (Telegram only)
- no commercial/labs/expert side effects

## 7) Exact local verification commands

```bash
pytest -q tests/test_reminder_materialization.py
pytest -q tests/test_health.py
pytest -q
```

Also available runtime command:

```bash
python -m scripts.dispatch_reminders
```
