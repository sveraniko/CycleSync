# PR W4 / PR3 — Reminder runtime hardening

## 1) Snooze semantics fixed

Before this PR, `snooze` action could lead to cleanup flow that eventually moved reminder into `cleaned`, which made it non-dispatchable.

Now `snooze` is explicitly non-terminal:
- reminder state becomes `snoozed`;
- `snoozed_until_utc` is set;
- old Telegram message is cleaned as UI hygiene only;
- reminder is not moved into terminal `cleaned` state;
- due selector can pick it again when `snoozed_until_utc <= now`.

## 2) Cleanup model separation

The model is now split into two layers:

- **runtime/business state** (`scheduled`, `awaiting_action`, `snoozed`, `completed`, `skipped`, `expired`, ...)
- **chat hygiene cleanup** (message cleanup timestamp + message reference invalidation)

For terminal outcomes (`completed`, `skipped`, `expired`) terminal cleanup can still move to `cleaned`.

For non-terminal `snoozed`, only message cleanup is applied (`mark_message_cleaned`), preserving runtime state as `snoozed`.

## 3) Re-delivery after snooze

Dispatch due selector already supports `snoozed` reminders. With fixed action/cleanup flow, this now works end-to-end:
1. reminder delivered;
2. user presses snooze;
3. old message gets invalidated;
4. reminder remains `snoozed`;
5. after snooze window, due selector claims reminder;
6. reminder is delivered again and returns to `awaiting_action`.

## 4) Canonical schedule anchor

Materialization fallback for entries without `scheduled_day` no longer uses `request.created_at.date()`.

New fallback anchor order:
1. `protocol.settings_snapshot_json.planned_start_date` (if present);
2. `protocol.activated_at.date()`;
3. `protocol.created_at.date()`.

This removes accidental dependence on reminder materialization request timing.

## 5) Added tests

Added targeted tests to cover:
- full snooze lifecycle with re-dispatch;
- cleanup separation behavior for snoozed reminders;
- anchor fallback behavior when `scheduled_day` is absent;
- precedence of explicit `scheduled_day` over fallback anchor.

## 6) Why W4 can be considered complete after this PR

This PR closes the runtime correctness gaps identified after W4/PR2:
- `Snooze` now behaves as postponement, not termination;
- chat cleanup no longer destroys reminder execution truth;
- schedule fallback anchor is stable and protocol-based;
- execution path is covered by targeted tests for re-delivery and anchoring.

As a result, Wave 4 reminder execution layer semantics are now consistent with lifecycle/state-machine documentation and operationally safe for moving into W5 scope.
