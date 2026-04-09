# CycleSync Reminders and Adherence

> Reminder system and adherence model document for **CycleSync**.

---

## 1. Purpose of this document

This document defines the reminder and adherence subsystem of CycleSync.

Its goals are to:

- formalize reminders as a core product feature, not a cosmetic add-on;
- define reminder lifecycle and user actions;
- define the separation between reminder state and adherence truth;
- define escalation, retry and expiration behavior;
- define how a protocol can be considered broken if execution discipline collapses;
- define settings and user control over reminders;
- prepare the foundation for implementation, workers, analytics and specialist visibility.

This document is **not**:

- a pulse-engine formula doc;
- a bot copywriting spec;
- a low-level worker cron spec;
- a deployment plan.

Those belong elsewhere.

---

## 2. Why reminders are one of the core product features

CycleSync does not sell “a beautiful calculation”.
It sells **an executable rhythm**.

That means the product promise is only fulfilled when:

1. the system computes a strong pulse plan;
2. the user is reminded at the right moment;
3. the system knows whether the user actually followed the plan.

Therefore reminders are not merely notifications.
They are the operational arm of the pulse engine.

And adherence is not merely activity logging.
It is the truth of whether the protocol still exists in real life or has already fallen apart.

---

## 3. Main principles

### 3.1 Reminders must be optional at settings level

A user must be able to turn reminders **on or off** in settings.

Reasons may include:

- the user no longer uses the service;
- the user stopped the protocol;
- the user does not want notifications for a period;
- the user switched to a different execution mode.

### 3.2 Reminder state is not adherence truth

Reminder system knows:

- what should happen;
- when it should happen;
- whether notification attempts were sent.

Adherence system knows:

- whether the user did it;
- skipped it;
- ignored it;
- broke the rhythm.

These must remain distinct.

### 3.3 A protocol can become broken

If the user accumulates too many missed/ignored/invalid reminder events, the system may conclude that the pulse plan is no longer being followed.

At that point the protocol may be marked:

- `broken`
- `deactivated`
- or equivalent status depending on final naming.

This is a key product feature, not a punishment gimmick.

### 3.4 Expired reminder messages should not clutter the chat

Old reminder messages should not hang in the chat forever if they are no longer actionable.

The system should prefer:

- editing active messages when possible;
- deleting expired reminder messages when safe to do so;
- keeping the chat clean.

### 3.5 Reminder system must not be passive

If the user does not respond, the system should not just shrug and walk away.

There must be:

- retry logic;
- escalation timing;
- expiry logic;
- broken-protocol logic.

---

## 4. Reminder system role in product architecture

Reminder system sits between:

- `Pulse Engine` (what should happen)
- `Adherence` (what actually happened)

It is derived from pulse-plan truth, but it is not itself the protocol truth.

Reminder subsystem is responsible for:

- generating executable reminder events from pulse-plan lines;
- scheduling delivery at the correct local time;
- handling retry/snooze/expiry behavior;
- exposing actions to the user;
- emitting adherence-relevant events;
- supporting protocol break detection.

---

## 5. Reminder types

CycleSync reminder model should support multiple event classes.

### 5.1 Core protocol reminders

These are the main reminders tied to pulse-plan execution.

Examples:

- scheduled injection/event reminder;
- next execution point reminder;
- rescheduled snoozed reminder.

### 5.2 Monitoring reminders

These may exist later or in limited MVP form.

Examples:

- time to upload labs;
- follow-up lab reminder;
- specialist-requested checkpoint.

### 5.3 System reminders

Examples:

- protocol broken/deactivated notice;
- reminder system disabled confirmation;
- protocol resumed notice.

MVP priority should remain on **core protocol reminders**.

---

## 6. Reminder settings model

## 6.1 User settings requirements

The user must be able to configure reminder behavior through settings.

Minimum settings:

- reminders enabled / disabled;
- preferred reminder hour or baseline delivery preference;
- timezone;
- maybe quiet mode later;
- maybe follow-up aggressiveness later.

### 6.2 Hard rule

If reminders are disabled:

- the reminder worker must not continue sending reminders;
- the protocol may remain stored, but execution automation is effectively paused;
- system should make it clear that protocol execution control is no longer active.

### 6.3 UI meaning of reminders off

Turning reminders off does not delete the protocol.
It means the user is choosing not to be actively guided by the system.

That should have downstream implications for adherence confidence.

---

## 7. Core reminder lifecycle

A reminder event should move through a defined lifecycle.

### 7.1 Suggested reminder states

Illustrative state set:

- `scheduled`
- `sent`
- `awaiting_action`
- `snoozed`
- `completed`
- `skipped`
- `expired`
- `cancelled`
- `deleted_from_chat` (delivery artifact state, not domain truth)

### 7.2 Reminder lifecycle flow

Typical flow:

1. pulse plan line exists;
2. reminder event is created;
3. notification is sent;
4. message is awaiting action;
5. user presses `Done`, `Snooze` or `Skip`;
6. adherence receives the action;
7. reminder closes or reschedules;
8. old message is cleaned up if no longer useful.

### 7.3 Important separation

`deleted_from_chat` is not the same as `expired`.

- `expired` is business state: the reminder can no longer be acted on in its intended window.
- `deleted_from_chat` is UI hygiene state: the message is no longer visible in Telegram.

---

## 8. Core user actions

Every active execution reminder should expose direct action buttons.

### 8.1 MVP actions

- `Done`
- `Snooze`
- `Skip`

### 8.2 Meaning of actions

#### `Done`

User confirms the scheduled action was completed.

#### `Snooze`

User delays the reminder for a short time window.

#### `Skip`

User explicitly states the scheduled action was not performed.

### 8.3 Why this matters

A reminder without an explicit action path is weak.

CycleSync must train execution discipline, not just throw messages into chat and hope the human species magically becomes reliable.

---

## 9. Reminder message behavior

## 9.1 Message content requirements

A reminder should tell the user:

- what needs to be done;
- when it should be done;
- context if needed (e.g. protocol stage or day);
- the action buttons.

### 9.2 Actionability rule

A reminder message should be actionable right inside Telegram.
The user should not need to navigate deep into menus just to confirm execution.

### 9.3 Message cleanup rule

When a reminder becomes obsolete, the system should clean the chat where possible.

Recommended strategy:

- active reminder message exists while the event is actionable;
- once resolved, expired or replaced, the old message is edited or deleted;
- stale reminder cards should not remain dangling in the chat.

### 9.4 Why delete expired messages

Because stale reminder messages create:

- confusion;
- noisy chat history;
- false action affordances;
- lower trust in the execution system.

---

## 10. Retry and escalation model

A core reminder must not vanish after one send if the user gives no response.

### 10.1 Retry principle

If the user does not respond, the system should retry according to a controlled retry policy.

### 10.2 Suggested retry phases

Illustrative model:

- initial reminder sent;
- first retry after a short grace period;
- second retry after a larger grace period;
- event marked expired / missed if still unanswered.

Exact timing belongs to implementation policy.

### 10.3 Retry limits

Retry logic should be finite.
The system must not spam indefinitely.

### 10.4 Escalation semantics

If repeated reminders receive no action:

- the event should become a negative adherence signal;
- the protocol health should degrade;
- repeated failures may contribute to `broken` detection.

---

## 11. Snooze model

### 11.1 Purpose

Snooze exists because reality is messy, but it must not become a loophole for infinite procrastination.

### 11.2 Snooze rules

Recommended product rules:

- snooze creates a rescheduled reminder instance or updates the existing reminder timing;
- snooze count should be tracked;
- snooze should be bounded in count and/or time window;
- excessive snooze may later count as adherence degradation if needed.

### 11.3 Why track snooze

Because repeated snoozing can mean:

- the schedule is impractical;
- the user is slipping;
- the protocol is becoming unreliable in practice.

---

## 12. Skip model

### 12.1 Purpose

Skip is not the same as silence.

It is explicit acknowledgement that the scheduled action did not happen.

### 12.2 Product meaning of skip

Skip should:

- immediately register as negative adherence;
- be visible in user history;
- be visible in specialist context later;
- contribute to protocol health scoring;
- possibly contribute to broken-protocol detection.

### 12.3 Skip is better than no signal

A user explicitly pressing `Skip` is operationally better than vanishing, because the system has truthful information.

---

## 13. Non-response model

Silence must be interpreted carefully.

### 13.1 Silence is not Done

If the user does nothing, the system must never infer successful completion.

### 13.2 Silence processing path

If there is no response:

- retry;
- retry again within policy;
- expire event;
- register unresolved/missed adherence signal.

### 13.3 Why silence matters

Because in a discipline-oriented system, non-response is not neutral.
It is information.

---

## 14. Adherence model

## 14.1 What adherence is

Adherence is the operational truth of whether the pulse plan is being followed.

### 14.2 Minimal adherence outcomes

For MVP, adherence can be built around:

- `done`
- `snoozed`
- `skipped`
- `missed` / `expired_with_no_action`

### 14.3 Reminder vs adherence distinction

Reminder tells us:

- what was scheduled;
- when it was sent;
- what messages were shown.

Adherence tells us:

- whether the user complied;
- delayed;
- explicitly skipped;
- ignored the event.

### 14.4 Why adherence is a product differentiator

Because CycleSync is not just “math with notifications”.
It is a **discipline system**.

That means execution quality must be measurable.

---

## 15. Protocol health and broken-state logic

This is one of the strongest product mechanics.

### 15.1 Why protocol health exists

A pulse plan only exists as long as the user is actually following it.

If the user repeatedly ignores or skips critical events, the plan may no longer represent reality.

### 15.2 Concept of protocol health

The system should maintain a derived concept such as:

- `healthy`
- `degrading`
- `at_risk`
- `broken`

These may be product-level statuses rather than direct protocol DB states initially.

### 15.3 Broken threshold concept

If a configurable number of critical misses/skips/non-responses is reached, the protocol can be considered **broken**.

Examples of triggers may later include:

- N unresolved execution reminders within a rolling window;
- N skips within a rolling window;
- consecutive missed critical events.

Exact thresholds belong to product policy / implementation config, but the architecture must support them.

### 15.4 Broken-state consequences

When a protocol becomes broken, the system may:

- stop or deactivate reminder automation;
- notify the user that the current pulse logic is no longer trustworthy;
- require explicit user action to resume;
- surface the issue in specialist context later.

### 15.5 Why this feature matters

Because without broken-state logic, the system would continue pretending the pulse plan is valid even after real execution collapsed.

That would make the product dishonest.

---

## 16. Protocol deactivation due to discipline failure

### 16.1 Deactivation concept

A protocol may be automatically deactivated if adherence quality drops below a defined threshold.

### 16.2 Product meaning

This does not mean the user can never continue.
It means:

- the current execution stream is no longer considered valid;
- reminder automation is stopped to avoid spamming nonsense;
- the user must consciously resume or rebuild the protocol context.

### 16.3 User-facing consequence

The system should clearly state something like:

- protocol execution is broken;
- reminders have been paused;
- resume/rebuild is required.

---

## 17. Resume / recovery model

If a protocol was broken or reminders were disabled, the system may later support recovery.

### 17.1 Recovery sources

Potential recovery triggers:

- user manually resumes reminders;
- user acknowledges broken state and asks to continue;
- specialist rebuilds or recalculates plan;
- a new protocol version supersedes the broken one.

### 17.2 Recovery rule

Recovery should not silently erase the previous broken-state history.

### 17.3 Recommended approach

The safer product approach is often:

- keep broken history;
- create a resumed or recalculated execution path;
- preserve continuity visibly.

---

## 18. Time and timezone model

### 18.1 Local-time expectation

Users experience reminders in local time, not UTC.

### 18.2 Storage rule

Recommended pattern:

- store canonical schedule timestamps in UTC;
- store user timezone separately;
- render/send reminders in local user time.

### 18.3 Why this matters

Because reminder trust is destroyed quickly when time semantics drift or appear random.

---

## 19. Reminder scheduling sources

The reminder subsystem should derive reminders from structured sources.

### 19.1 Primary source

- pulse-plan lines

### 19.2 Secondary sources

Later:

- lab follow-up events;
- specialist-requested checkpoints;
- recovery/resume tasks.

### 19.3 Important rule

Reminder events must not be manually improvised from chat state or UI fragments.
They must derive from domain truth.

---

## 20. Specialist visibility

Specialist workflows later should be able to see:

- protocol reminder history;
- done/skip/missed patterns;
- recent broken-state transitions;
- whether the user disabled reminders;
- execution confidence.

This is important because labs and risk interpretation are meaningless if actual execution discipline is unknown.

---

## 21. Analytics for reminders and adherence

The system should track reminder/adherence metrics from day one.

### 21.1 Useful metrics

- reminders sent;
- done rate;
- snooze rate;
- skip rate;
- non-response rate;
- broken-protocol rate;
- disabled-reminders rate;
- time-to-response;
- per-preset adherence distribution.

### 21.2 Why this matters

Reminder quality is product quality in CycleSync.
If reminder behavior is weak, the pulse engine loses real-world value.

---

## 22. Data model implications

Reminder and adherence subsystem should map into explicit data structures such as:

- `ReminderEvent`
- `ReminderDispatch`
- `AdherenceAction`
- `AdherenceSnapshot`
- `ProtocolHealthState` or equivalent derived projection

### 22.1 Important modeling rule

Do not store everything inside one bloated reminder table.

At minimum, preserve distinction between:

- scheduled event;
- dispatch attempts;
- user action/adherence truth;
- derived health state.

---

## 23. Bot-flow implications

Reminder UX must support:

- one-tap action buttons;
- clear current-state feedback;
- cleanup of stale messages;
- no chat pollution from dead reminder cards;
- consistent behavior when multiple events exist near each other.

### 23.1 Clean-chat principle

CycleSync should treat reminder messages as operational cards, not permanent chat decoration.

### 23.2 Expired-message cleanup principle

An expired or superseded reminder card should be:

- edited into resolved state; or
- deleted from chat if no longer useful.

The product should prefer a clean operational chat.

---

## 24. Reminder/adherence guardrails

The subsystem must avoid the following mistakes.

### 24.1 Notification-only illusion

Do not confuse “message was sent” with “execution happened”.

### 24.2 Infinite spam loop

Do not retry forever with no stop condition.

### 24.3 Broken-state denial

Do not continue pretending the pulse plan is valid after repeated execution failure.

### 24.4 Reminder-disable ambiguity

Do not let the user disable reminders without clear product consequences.

### 24.5 Chat clutter

Do not leave dead action cards piling up in chat.

### 24.6 Adherence without history

Do not compress adherence truth so aggressively that specialist review later loses meaning.

---

## 25. Recommended future dependent documents

This reminder/adherence document should feed the creation of:

- `docs/56_reminder_state_machine.md`
- `docs/57_protocol_health_rules.md`
- `docs/58_reminder_worker_policy.md`
- `docs/60_labs_ai_and_expert_cases.md`
- `docs/70_analytics.md`

These names are recommendations and may change.

---

## 26. Final reminder/adherence statement

CycleSync reminders are not passive notifications.
They are the operational execution layer of the pulse engine.

Adherence is not activity fluff.
It is the truth of whether the protocol is still being followed.

The subsystem must therefore:

- allow user control through settings;
- send actionable reminders;
- require explicit response where possible;
- retry intelligently;
- clean up stale messages;
- track done / snooze / skip / no-response;
- detect when execution is collapsing;
- and, if necessary, mark the protocol as broken and stop pretending everything is fine.

That is what turns CycleSync from a “calculator with messages” into a real discipline system.
