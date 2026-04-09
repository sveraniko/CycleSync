# CycleSync Reminder State Machine

> Reminder state-machine document for **CycleSync**.

---

## 1. Purpose of this document

This document defines the state machine of reminder events in CycleSync.

Its goals are to:

- formalize reminder lifecycle states and transitions;
- separate reminder state from adherence truth;
- define what happens after send, snooze, skip, no-response and expiry;
- define which transitions are valid and which are not;
- support implementation of reminder workers, UI actions and cleanup behavior.

This document is **not**:

- a pulse-engine scheduling formula document;
- a low-level Telegram API retry document;
- a product copywriting spec;
- a full adherence scoring document.

Those belong elsewhere.

---

## 2. Why a state machine is required

CycleSync reminders are not passive messages.
They are executable protocol events with user actions, retries, expiry and protocol-health consequences.

Without a formal state machine, reminder handling drifts into chaos:

- duplicate sends;
- impossible transitions;
- ambiguous UI state;
- dead cards in chat;
- broken analytics;
- wrong adherence interpretation.

This document exists to prevent that.

---

## 3. Core principle

The central rule is:

> **Reminder state tracks the lifecycle of the scheduled execution event. It does not replace adherence truth.**

This means:

- reminder state answers “where is this scheduled event in the reminder workflow?”
- adherence answers “what did the user actually do?”

These are linked, but they are not the same thing.

---

## 4. Reminder event lifecycle scope

A reminder event begins when a pulse-plan-derived execution point is materialized into a reminder.

It ends when the reminder becomes resolved, expired, cancelled or otherwise no longer actionable.

The reminder state machine applies to the reminder event itself, not to:

- protocol truth;
- pulse plan truth;
- adherence score;
- commercial entitlement.

---

## 5. Recommended reminder states

The state machine should use a clear, explicit set of reminder states.

### 5.1 `scheduled`

The reminder exists and is waiting for send time.

### 5.2 `sent`

The reminder message was sent to the user successfully.

### 5.3 `awaiting_action`

The reminder is visible and still actionable.

### 5.4 `snoozed`

The user explicitly delayed action and the reminder is waiting for the next attempt window.

### 5.5 `completed`

The reminder reached a resolved state because the user completed the scheduled action.

### 5.6 `skipped`

The reminder reached a resolved state because the user explicitly skipped the scheduled action.

### 5.7 `expired`

The reminder is no longer actionable within its intended execution window.

### 5.8 `cancelled`

The reminder was intentionally invalidated due to upstream lifecycle change.

Examples:

- protocol cancelled;
- pulse plan superseded;
- reminders disabled before send;
- protocol deactivated/broken.

### 5.9 `cleaned`

The chat message or visible reminder card was removed/edited as part of cleanup.

Important: this is a reminder delivery/UI artifact state, not adherence truth.

---

## 6. State semantics

### 6.1 `scheduled`

Meaning:

- reminder has been created from domain truth;
- it is not yet delivered;
- it is waiting for dispatch time.

### 6.2 `sent`

Meaning:

- the system successfully issued a delivery attempt;
- the reminder exists in user chat or equivalent delivery surface.

### 6.3 `awaiting_action`

Meaning:

- the reminder is live;
- the user may still press `Done`, `Snooze` or `Skip`.

In practice `sent` and `awaiting_action` may happen very close together, but they are semantically distinct.

### 6.4 `snoozed`

Meaning:

- the user acknowledged the reminder;
- the user did not complete or skip the action yet;
- a future reminder instance or rescheduled state will follow.

### 6.5 `completed`

Meaning:

- the reminder is resolved through explicit user completion.

### 6.6 `skipped`

Meaning:

- the reminder is resolved through explicit non-execution.

### 6.7 `expired`

Meaning:

- the system did not receive a valid terminal action inside the allowed execution window.

### 6.8 `cancelled`

Meaning:

- the reminder is no longer valid due to upstream state changes, not because the user completed/skipped it.

### 6.9 `cleaned`

Meaning:

- the visible Telegram card/message has been cleaned up.
- this does **not** redefine the underlying business resolution by itself.

---

## 7. Reminder state transition graph

A simplified valid transition graph:

- `scheduled` -> `sent`
- `sent` -> `awaiting_action`
- `awaiting_action` -> `snoozed`
- `awaiting_action` -> `completed`
- `awaiting_action` -> `skipped`
- `awaiting_action` -> `expired`
- `snoozed` -> `scheduled` or `sent` (depending on implementation model)
- `scheduled` -> `cancelled`
- `sent` -> `cancelled`
- `awaiting_action` -> `cancelled`
- `completed` -> `cleaned`
- `skipped` -> `cleaned`
- `expired` -> `cleaned`
- `cancelled` -> `cleaned`

Exact implementation may normalize some of these states differently, but the semantics must remain stable.

---

## 8. Creation rule

### 8.1 Source of creation

A reminder event must originate from valid domain truth such as:

- pulse-plan line;
- lab follow-up rule later;
- specialist follow-up request later.

### 8.2 Initial state

A newly created reminder enters `scheduled`.

### 8.3 Important rule

Reminders must not be created ad hoc from chat/UI state without domain linkage.

---

## 9. Send rule

### 9.1 Scheduled -> Sent

A reminder transitions from `scheduled` to `sent` when the system performs a successful delivery attempt.

### 9.2 Sent -> Awaiting action

Once the message is in the user’s active interaction space, the reminder becomes actionable.

This is the point where the user can:

- press `Done`
- press `Snooze`
- press `Skip`

### 9.3 Important rule

A failed dispatch does not justify moving the reminder into `sent`.

---

## 10. Snooze transitions

### 10.1 Awaiting_action -> Snoozed

Triggered when the user explicitly presses `Snooze`.

### 10.2 Snoozed follow-up behavior

A snoozed reminder must later re-enter the active send/schedule path.

Two acceptable implementation interpretations:

- model the same reminder as returning to `scheduled` with updated time;
- keep state `snoozed` until re-dispatch moves it to `sent` again.

### 10.3 Important rule

Snooze is not terminal.
It does not complete or skip the protocol event.

---

## 11. Completion transitions

### 11.1 Awaiting_action -> Completed

Triggered when the user explicitly presses `Done`.

### 11.2 Consequences

- reminder becomes terminally resolved;
- adherence layer records `done`;
- cleanup may happen later;
- no further reminder retry should occur for this event.

---

## 12. Skip transitions

### 12.1 Awaiting_action -> Skipped

Triggered when the user explicitly presses `Skip`.

### 12.2 Consequences

- reminder becomes terminally resolved;
- adherence layer records `skip`;
- protocol health may degrade;
- cleanup may happen later.

### 12.3 Important rule

`skipped` is a truthful terminal state, not a transport failure.

---

## 13. Expiry transitions

### 13.1 Awaiting_action -> Expired

Triggered when the reminder has exceeded its useful action window with no valid terminal response.

### 13.2 Consequences

- adherence layer should record non-response / missed behavior;
- reminder is no longer actionable;
- stale card should be cleaned up;
- protocol health may degrade.

### 13.3 Important rule

Expired is different from skipped:

- `skipped` = user explicitly said “I did not do it”
- `expired` = user provided no valid final response in time

---

## 14. Cancellation transitions

### 14.1 States that may transition to cancelled

A reminder may move into `cancelled` from:

- `scheduled`
- `sent`
- `awaiting_action`
- `snoozed`

### 14.2 Cancellation causes

Examples:

- protocol cancelled;
- protocol paused/deactivated;
- pulse plan superseded;
- reminders disabled;
- broken-protocol state triggered and automation stopped.

### 14.3 Important rule

Cancelled means the reminder was invalidated by system/domain changes, not user completion.

---

## 15. Cleanup transitions

### 15.1 Why cleanup exists

CycleSync should not leave dead reminder cards cluttering the chat.

### 15.2 Terminal states eligible for cleanup

A reminder may transition into `cleaned` after:

- `completed`
- `skipped`
- `expired`
- `cancelled`

### 15.3 Meaning of cleaned

The user-facing message/card has been edited or deleted.
This is a delivery/UI hygiene result, not a domain substitute for the prior terminal state.

### 15.4 Important rule

Do not use `cleaned` as if it were the only final business state.
The system must still know whether the reminder ended as completed, skipped, expired or cancelled.

---

## 16. Invalid transitions

The following transitions should not happen silently.

Examples:

- `scheduled` -> `completed` without send/action path
- `scheduled` -> `skipped` without explicit user action or explicit admin/system override model
- `completed` -> `awaiting_action`
- `skipped` -> `awaiting_action`
- `expired` -> `completed`
- `cancelled` -> `completed`
- `cleaned` -> `awaiting_action`

If any special recovery flow is added later, it must create explicit new reminder lifecycle logic rather than abusing invalid transitions.

---

## 17. Retry model and state machine relation

Retries affect delivery attempts, but do not necessarily require new business states each time.

### 17.1 Retry rule

A retry should usually operate inside the `scheduled`/`sent`/`awaiting_action` lifecycle, depending on implementation policy.

### 17.2 Important distinction

- retry count is delivery mechanics;
- reminder state is lifecycle semantics.

Do not explode the state machine with transport-specific pseudo-states unless truly necessary.

---

## 18. Reminder state and adherence relation

### 18.1 Mapping examples

- `completed` -> adherence `done`
- `skipped` -> adherence `skip`
- `expired` -> adherence `missed`
- `snoozed` -> adherence may stay non-terminal until a final outcome exists

### 18.2 Important rule

Reminder state machine must never collapse into adherence truth.

The same reminder can have:

- one business lifecycle;
- one or more dispatch attempts;
- one eventual adherence outcome.

These are linked but distinct concerns.

---

## 19. Broken-protocol relation

### 19.1 Why this matters

A single reminder does not define protocol health.
But repeated transitions into:

- `skipped`
- `expired`
- unresolved cycles

may contribute to protocol degradation and later `broken` state.

### 19.2 Rule

Reminder terminal states must be available to protocol-health logic, but reminder state machine itself should not try to store full protocol-health semantics.

---

## 20. State timestamps

The reminder system should preserve important timestamps such as:

- scheduled_at / scheduled_for
- sent_at
- snoozed_at
- action_taken_at
- expired_at
- cancelled_at
- cleaned_at

These timestamps are important for:

- analytics;
- debugging;
- specialist context later;
- rebuild/repair logic.

---

## 21. Message cleanup rule

### 21.1 Clean-chat principle

CycleSync should treat reminder messages as operational cards, not permanent chat history clutter.

### 21.2 Cleanup rule

When a reminder is terminally resolved or no longer valid, the system should:

- edit the card to resolved form; or
- delete the old card where appropriate.

### 21.3 Important rule

Cleanup should happen after business state resolution, not instead of it.

---

## 22. State-machine guardrails

The reminder state machine must avoid the following mistakes.

### 22.1 Reminder/adherence collapse

Do not treat reminder states as if they were the full compliance truth.

### 22.2 Delivery-state explosion

Do not pollute the business state machine with every transport-level nuance.

### 22.3 Silent invalid transitions

Do not let terminal states reopen without explicit lifecycle semantics.

### 22.4 Cleanup-as-business-truth

Do not confuse deleted message/card state with reminder outcome.

### 22.5 Retry confusion

Do not let retries silently create duplicate live reminders for one scheduled event.

---

## 23. Relationship to other docs

This document depends on and supports:

- `45_protocol_lifecycle.md`
- `50_pulse_engine.md`
- `55_reminders_and_adherence.md`
- `71_event_catalog.md`
- `74_projection_rebuild_rules.md`
- `76_outbox_and_delivery_policy.md`

It provides the formal state semantics needed for reminder implementation.

---

## 24. Final statement

CycleSync reminder events must have an explicit lifecycle because they are one of the product’s core execution features.

A reminder is not just “sent or not sent”.
It moves through a controlled state machine that distinguishes:

- scheduled;
- delivered and actionable;
- snoozed;
- completed;
- skipped;
- expired;
- cancelled;
- cleaned.

This is what keeps reminder behavior explainable, testable and trustworthy.
