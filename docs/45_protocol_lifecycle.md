# CycleSync Protocol Lifecycle

> Protocol lifecycle and user-flow document for **CycleSync**.

---

## 1. Purpose of this document

This document defines the lifecycle of a protocol in CycleSync.

Its goals are to:

- describe how a user moves from search to calculation;
- formalize the states of protocol creation, calculation, confirmation and execution;
- define the relationship between draft, protocol, pulse plan, reminders and adherence;
- describe lifecycle events and transition rules;
- define when recalculation is allowed and how historical truth is preserved;
- prepare the foundation for bot flows, state machines and implementation.

This document is **not**:

- a formula-level pulse algorithm document;
- a detailed reminder state machine;
- a UI pixel/spec document;
- a testing plan.

Those should be covered elsewhere.

---

## 2. Core lifecycle principle

CycleSync protocol lifecycle must reflect the product’s central promise:

> **The user selects compounds and protocol constraints, the system computes the pulse plan, and execution is then enforced through reminders and adherence tracking.**

This means:

- search is the entry point;
- draft is the preparation space;
- protocol is the declared intent;
- pulse plan is the computed truth of execution rhythm;
- reminders are the timed operationalization of that truth;
- adherence is the record of what really happened.

These are not the same thing and must not collapse into one “generic flow”.

---

## 3. Main lifecycle objects

The lifecycle revolves around the following objects:

### `Calculation Draft`

A temporary preparation context where the user collects compounds before protocol confirmation.

### `Protocol`

The user’s declared plan, including:

- selected compounds;
- weekly target;
- duration;
- preset;
- constraints.

### `Pulse Plan`

The computed scheduling artifact generated from the protocol.

### `Reminder Chain`

The timed event stream derived from the pulse plan.

### `Adherence History`

The factual record of done / snooze / skip and related execution behavior.

### `Lab Context`

The observation layer attached to protocol execution later.

### `Expert Case`

A human escalation object built on top of protocol, adherence and lab history.

---

## 4. Lifecycle stages at high level

A protocol moves through the following major stages:

1. **Search & Drafting**
2. **Protocol Draft Formation**
3. **Calculation**
4. **Protocol Confirmation**
5. **Activation**
6. **Execution via Reminders**
7. **Adherence Tracking**
8. **Recalculation / Adjustment (if needed)**
9. **Completion / Pause / Cancel / Archive**
10. **Optional Labs / AI / Expert Escalation**

---

## 5. Stage 1 — Search & Drafting

### 5.1 Entry point

CycleSync starts from **search**, not from catalog browsing.

The user:

- searches by product name;
- searches by brand + product;
- searches by active ingredient / ester;
- searches by composition/dosage;
- optionally uses voice.

### 5.2 Search results

Each result supports:

- `Open`
- `+Draft`

### 5.3 Role of `+Draft`

When the user clicks `+Draft`, the system adds a concrete `compound_id` to the calculation draft context.

This is not a shopping cart and not a free-text list.

### 5.4 Not-found behavior

If a query is not found:

- the system explicitly reports no match;
- the query is logged;
- optional alternative-finding logic may be offered later.

---

## 6. Stage 2 — Calculation Draft Formation

### 6.1 What a draft is

A calculation draft is a temporary workspace where the user assembles candidate compounds before committing to a protocol.

### 6.2 Draft responsibilities

The draft may contain:

- selected compounds;
- notes or temporary ordering;
- unresolved items;
- a pending weekly target;
- duration;
- selected preset;
- max volume / max frequency constraints;
- warnings if the set is incomplete.

### 6.3 Draft is not protocol truth

A calculation draft must remain clearly distinct from a protocol.

Drafts are:

- editable;
- disposable;
- revisable;
- incomplete by design.

Protocols are not.

### 6.4 Draft actions

Possible actions:

- add compound;
- remove compound;
- reorder compound list;
- inspect compound card;
- define weekly target;
- define duration;
- define constraints;
- choose preset;
- calculate preview.

### 6.5 Draft exit conditions

A draft is ready to calculate when at least:

- one or more valid compounds are selected;
- weekly target exists;
- duration exists;
- preset exists or a default is applied.

---

## 7. Stage 3 — Calculation

### 7.1 What happens at calculation time

At calculation time:

- the system reads draft contents;
- validates required fields;
- resolves compound catalog truth;
- applies preset logic;
- runs pulse-engine calculation;
- produces a **Pulse Plan Preview**.

### 7.2 What calculation produces

The calculation output should include:

- resulting pulse-plan;
- calendar preview;
- frequency summary;
- volume summary;
- flatness/stability indicators if available;
- warnings or conflicts;
- whether the plan respects volume/frequency constraints.

### 7.3 Calculation does not yet activate execution

A successful calculation does **not** automatically start reminders or adherence tracking.

Calculation creates a preview or candidate plan that still requires confirmation.

### 7.4 Calculation failure paths

Examples:

- impossible volume constraints;
- invalid or missing half-life data;
- unsupported compound data;
- impossible preset under current limits.

In such cases the draft remains editable and the user is returned to correction flow.

---

## 8. Stage 4 — Protocol Confirmation

### 8.1 Why confirmation is a separate stage

Protocol confirmation is the point where:

- the user accepts the computed plan;
- draft becomes protocol truth;
- execution responsibility begins.

This stage must be explicit.

### 8.2 Confirmation side effects

When the user confirms:

- a `Protocol` is created or finalized;
- a `Pulse Plan` becomes the current authoritative plan for execution;
- reminder generation becomes eligible;
- the protocol enters `confirmed` or directly `active` depending on timing rules.

### 8.3 Confirmation lock-in principle

After confirmation:

- historical calculation truth must be preserved;
- major edits should not mutate the existing plan silently;
- material changes must cause recomputation and/or a new protocol revision.

---

## 9. Stage 5 — Activation

### 9.1 What activation means

Activation means the protocol becomes operational in time.

This may happen:

- immediately after confirmation if start date is today;
- on scheduled start date if the protocol starts later.

### 9.2 Activation side effects

When a protocol becomes active:

- reminder events are materialized or released into active scheduling;
- the system begins adherence tracking;
- the protocol appears in active user context;
- labs uploaded later can be tied to the active protocol context.

### 9.3 Important rule

A confirmed protocol that starts in the future is not yet an active execution object.

---

## 10. Stage 6 — Execution through reminders

### 10.1 Reminders operationalize the plan

Once active, execution is driven through reminders derived from the pulse plan.

### 10.2 Reminder actions

For each relevant reminder the user should be able to choose:

- `Done`
- `Snooze`
- `Skip`

### 10.3 Reminder role in lifecycle

Reminder is the operational bridge between:

- static computed plan;
- actual time-bound user behavior.

### 10.4 Reminder chain generation

A reminder chain should be generated from pulse-plan lines and related follow-up rules.

Examples:

- injection reminders;
- analysis reminders later;
- specialist follow-up reminders later.

---

## 11. Stage 7 — Adherence tracking

### 11.1 Adherence is separate from reminders

Reminder answers are converted into adherence truth.

Reminder knows:

- what was scheduled;
- what was sent.

Adherence knows:

- what the user actually did.

### 11.2 Adherence outcomes

At minimum:

- done
- snoozed
- skipped

Later extensions may include:

- done late
- partial execution
- broken sequence

### 11.3 Why adherence matters in lifecycle

Because the product promise is not just “calculate”, but “calculate and actually hold the rhythm”.

Adherence becomes part of:

- user history;
- protocol quality;
- lab interpretation context;
- specialist case context.

---

## 12. Stage 8 — Recalculation / Adjustment

### 12.1 Why recalculation exists

Recalculation is necessary when material conditions change.

Examples:

- protocol compounds changed;
- weekly target changed;
- duration changed;
- preset changed;
- max volume / frequency changed;
- specialist intervened;
- a later controlled feature supports mid-cycle adjustment.

### 12.2 Recalculation rule

Recalculation must produce:

- a new pulse plan;
- explicit supersession of the old plan if it was active;
- revised reminder chain where appropriate;
- preserved historical reference to old plan truth.

### 12.3 Draft-vs-active recalculation distinction

If the protocol is still draft/not started:

- recalculation can remain cheap and revision-light.

If the protocol is active:

- recalculation is a serious transition;
- the system must not silently rewrite history;
- reminders and adherence context must remain explainable.

### 12.4 User-initiated vs specialist-initiated recalculation

Normal users should have limited freedom.

Later specialist mode may allow deeper adjustments.

But in all cases, recalculation must remain traceable.

---

## 13. Stage 9 — Completion, pause, cancel, archive

### 13.1 Completion

A protocol reaches `completed` when:

- its intended duration is fulfilled; or
- it is explicitly marked complete at the end of the cycle.

Completion does not erase:

- pulse plan history;
- reminders history;
- adherence history;
- lab linkage.

### 13.2 Pause

A protocol may be paused if that becomes a supported feature.

Pause means:

- the protocol is temporarily not actively executed;
- reminders may be suspended;
- history remains intact.

### 13.3 Cancel

Cancel applies when the protocol is abandoned before completion.

The system must preserve why and when this happened.

### 13.4 Archive

Archive is a storage/view concern applied to historical protocols.

Archived protocols are no longer part of the active surface but remain queryable.

---

## 14. Stage 10 — Labs, AI and expert escalation

### 14.1 Labs are attached to lifecycle, not detached from it

Labs do not exist in a vacuum.

They become useful when tied to:

- an active or recent protocol;
- adherence behavior;
- time on protocol.

### 14.2 AI role in lifecycle

AI does not create or define the protocol lifecycle.

AI enters after enough execution history exists and produces:

- preliminary assessment;
- trend signals;
- possible risk flags;
- structured specialist context.

### 14.3 Expert escalation

When needed, an expert case can be opened from:

- protocol context;
- lab context;
- adherence context;
- AI assessment context.

The expert case is therefore a downstream lifecycle object, not the origin of protocol truth.

---

## 15. Core protocol states

The protocol lifecycle should support explicit states.

Illustrative state universe:

- `draft`
- `calculated`
- `confirmed`
- `scheduled`
- `active`
- `paused`
- `completed`
- `cancelled`
- `archived`

The exact final set may be simplified later, but the distinctions matter.

### 15.1 Suggested semantics

#### `draft`

User is still assembling compounds and settings.

#### `calculated`

A pulse-plan preview exists, but the protocol is not yet confirmed.

#### `confirmed`

User accepted the plan, but it may not yet be active in time.

#### `scheduled`

Protocol is confirmed and waiting for future start date.

#### `active`

Execution is live; reminders/adherence are running.

#### `paused`

Temporarily suspended.

#### `completed`

Planned cycle completed.

#### `cancelled`

Protocol intentionally stopped or discarded after confirmation.

#### `archived`

Historical storage/view state.

---

## 16. Lifecycle transitions

### 16.1 Main transition path

Typical path:

`draft` -> `calculated` -> `confirmed` -> `scheduled|active` -> `completed|cancelled` -> `archived`

### 16.2 Valid transitions (illustrative)

Allowed examples:

- `draft` -> `calculated`
- `calculated` -> `draft`
- `calculated` -> `confirmed`
- `confirmed` -> `scheduled`
- `confirmed` -> `active`
- `scheduled` -> `active`
- `active` -> `paused`
- `paused` -> `active`
- `active` -> `completed`
- `active` -> `cancelled`
- `completed` -> `archived`
- `cancelled` -> `archived`

### 16.3 Invalid transition examples

Examples of transitions that should not happen silently:

- `draft` -> `active`
- `active` -> `draft`
- `completed` -> `draft`
- `cancelled` -> `active` without explicit recovery flow

---

## 17. Lifecycle events

The lifecycle should emit meaningful events such as:

- `protocol_created`
- `protocol_updated`
- `protocol_calculated`
- `protocol_confirmed`
- `protocol_scheduled`
- `protocol_activated`
- `pulse_plan_computed`
- `pulse_plan_superseded`
- `reminder_scheduled`
- `reminder_sent`
- `reminder_done`
- `reminder_snoozed`
- `reminder_skipped`
- `protocol_paused`
- `protocol_completed`
- `protocol_cancelled`
- `lab_uploaded`
- `ai_assessment_created`
- `expert_case_opened`

These events later feed analytics, specialist summaries and projection rebuilds.

---

## 18. Lifecycle ownership boundaries

The protocol lifecycle crosses multiple contexts, but ownership must remain explicit.

### `Draft`

Owned by the preparation flow / protocol preparation layer.

### `Protocol`

Owned by `Protocols` context.

### `Pulse Plan`

Owned by `Pulse Engine` context.

### `Reminder Chain`

Owned by `Reminders` context.

### `Adherence Truth`

Owned by `Adherence` context.

### `Lab History`

Owned by `Labs` context.

### `AI Assessment`

Owned by `AI Triage` context.

### `Expert Case`

Owned by `Expert Cases` context.

No single lifecycle handler should pretend to own all these at once.

---

## 19. Search-to-protocol relation

Because CycleSync is search-first, lifecycle must acknowledge that protocol creation begins with search.

### 19.1 Search is not protocol

Search retrieves compounds.
It does not create protocol truth by itself.

### 19.2 `+Draft` is not confirmation

Adding a compound to draft is only preparation.
It must not be mistaken for:

- a committed protocol;
- an active plan;
- an adherence obligation.

### 19.3 Draft is the bridge

Draft is the boundary between search and protocol creation.

---

## 20. Reminder-to-adherence relation

### 20.1 Reminder event

Represents a scheduled execution point.

### 20.2 Adherence action

Represents what the user actually did.

### 20.3 Lifecycle rule

A reminder event without adherence action means the system knows the execution point existed, but not that the user followed it.

A skipped reminder is different from a missing reminder.

This distinction must remain visible in lifecycle semantics.

---

## 21. Revisions and historical truth

### 21.1 Why revisions matter

CycleSync is not a one-shot calculator.
A user may:

- revise before confirmation;
- recalculate after changing inputs;
- later need specialist-guided adjustments.

### 21.2 Historical truth rules

The system must preserve:

- old pulse-plan versions;
- state changes;
- reminder history;
- adherence history;
- lab history;
- expert-case history.

### 21.3 What must not happen

The system must not rewrite an already-executed past as if the new plan had always existed.

---

## 22. Lifecycle guardrails

The lifecycle must avoid the following mistakes.

### 22.1 Draft/Protocol collapse

Do not treat temporary draft state as confirmed protocol truth.

### 22.2 Protocol/PulsePlan collapse

Do not treat protocol inputs and computed pulse-plan as the same thing.

### 22.3 Reminder/Adherence collapse

Do not use reminder state as a shortcut for what the user actually did.

### 22.4 Recalculation-as-overwrite

Do not let recalculation silently overwrite past plans.

### 22.5 Labs detached from protocol history

Do not treat labs as context-free uploads unrelated to execution history.

### 22.6 Expert-case inversion

Do not let specialist escalation become the hidden real lifecycle while protocol execution becomes secondary.

---

## 23. Recommended future dependent documents

This lifecycle document should feed the creation of:

- `docs/46_draft_flow.md`
- `docs/47_protocol_state_machine.md`
- `docs/50_pulse_engine.md`
- `docs/55_reminders_and_adherence.md`
- `docs/60_labs_ai_and_expert_cases.md`
- `docs/70_analytics.md`

These names are recommendations and can be adjusted.

---

## 24. Final lifecycle statement

CycleSync protocol lifecycle must preserve the sequence:

**Search -> Draft -> Calculation -> Confirmation -> Activation -> Reminders -> Adherence -> Observation -> Optional escalation**

This sequence expresses the product truth.

The user does not directly “live inside the algorithm”.  
The user interacts through search, draft and execution.  
The system converts that into a computed pulse plan and enforces it over time.

This document defines the operational spine of protocol execution in CycleSync.
