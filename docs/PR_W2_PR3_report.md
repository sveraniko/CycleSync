# PR_W2_PR3 — Protocol Promotion / Activation Foundation

## Что реализовано

### 1) Active protocol truth (отдельно от draft/preview)

Добавлены новые activation-объекты:

- `protocols.protocols` — lifecycle truth уровня protocol (`preview_ready` / `active` / `superseded` / `cancelled`);
- `pulse_engine.pulse_plans` — активный pulse plan, связанный с protocol;
- `pulse_engine.pulse_plan_entries` — materialized active schedule entries;
- `reminders.reminder_schedule_requests` — seam-таблица для запроса генерации reminder schedule (без delivery/adherence логики).

Также `pulse_engine.pulse_plan_previews` получил `lifecycle_status` и `superseded_at`, чтобы preview truth не смешивался с active truth.

### 2) Promotion flow preview -> active

В application service добавлен explicit activation шаг:

- `confirm_latest_preview_activation(user_id)`:
  1. берет последний `preview_ready` protocol;
  2. supersede-ит предыдущий `active` protocol пользователя;
  3. переводит выбранный protocol в `active`;
  4. materialize-ит `pulse_engine.pulse_plans` + `pulse_plan_entries` из preview entries;
  5. создает `reminder_schedule_requests` (generation seam);
  6. эмитит activation events.

При генерации нового preview:

- предыдущие `preview_ready` protocols по draft переводятся в `superseded`;
- их source previews помечаются `superseded`.

### 3) Explicit lifecycle states

В PR3 lifecycle foundation использует явные статусы:

- `draft` — рабочий расчетный контекст;
- `preview_ready` — подтверждаемый protocol/preview;
- `active` — protocol и pulse plan активированы;
- `superseded` — заменен более новым preview/protocol;
- `cancelled` — зарезервирован под явную отмену (hook для следующих шагов lifecycle).

### 4) Reminder seam

Полная reminder delivery/escalation/adherence логика **не** внедрялась.

Сделан только seam:

- persisted request: `reminders.reminder_schedule_requests`;
- event hook: `reminder_schedule_requested`.

Это позволяет Wave 3 построить scheduler/worker поверх активного protocol truth без перепридумывания activation.

### 5) Bot UX

После preview пользователь теперь может:

- нажать `Подтвердить и активировать`;
- получить подтверждение `Protocol activated`;
- увидеть короткий active summary (preset, duration, weekly target);
- получить явный handoff, что execution/reminders продолжатся на следующей волне.

### 6) Events

Добавлены/задействованы hooks:

- `protocol_activated`
- `pulse_plan_activated`
- `protocol_superseded`
- `reminder_schedule_requested`

`protocol_cancelled` оставлен как lifecycle hook для следующего шага PR/Wave (без полной cancellation UX в этом PR).

## Что сознательно НЕ реализовано в PR3

- full reminder delivery/dispatch/retry/escalation;
- reminder state machine runtime;
- adherence scoring / broken protocol automation;
- labs/expert/commercial контуры.

## Что идет в Wave 3

- материализация reminder rows из `reminder_schedule_requests`;
- reminder state machine transitions (`scheduled/sent/awaiting_action/snoozed/...`);
- delivery workers + retry/escalation/expiry;
- user actions (`Done/Snooze/Skip`) и binding к adherence truth;
- protocol cancellation UX + `protocol_cancelled` end-to-end flow.
