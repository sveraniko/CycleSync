# CycleSync Outbox and Delivery Policy

> Outbox, event delivery and retry policy document for **CycleSync**.

---

## 1. Purpose of this document

This document defines how CycleSync should persist, publish and deliver meaningful events to downstream consumers.

Its goals are to:

- formalize the outbox pattern for reliable event delivery;
- define delivery guarantees and retry expectations;
- define what kinds of events belong in outbox processing;
- define idempotency and de-duplication rules;
- define how failed deliveries and stuck events are handled;
- support stable projections, analytics, reminders and other downstream consumers.

This document is **not**:

- a message broker selection document;
- a queue vendor benchmark;
- a full DevOps runbook;
- a log aggregation document.

Those should be specified elsewhere if needed.

---

## 2. Why outbox is needed in CycleSync

CycleSync already depends on multiple downstream reactions to core product events.

Examples:

- protocol confirmation should trigger pulse-plan and/or execution-related downstream updates;
- pulse-plan changes may lead to reminder scheduling updates;
- adherence actions affect protocol-health projections and analytics;
- lab report completion may trigger AI triage;
- specialist and commercial flows also depend on reliable event propagation.

If these side effects are implemented as fragile inline code paths only, the system becomes vulnerable to:

- partial failures;
- duplicate side effects;
- lost analytics;
- stale projections;
- inconsistent reminder/protocol state.

The outbox pattern exists to prevent that.

---

## 3. Core principle

The central rule is:

> **Commit transactional truth first. Publish downstream effects from a reliable outbox second.**

This means:

- core state changes happen in the transactional database;
- corresponding events are persisted in the same logical transaction or equivalent durable step;
- a separate delivery process publishes them to consumers;
- downstream consumers remain retryable and idempotent.

---

## 4. Scope of outbox usage

Not every technical log line belongs in outbox.

The outbox is for **meaningful domain/application events** that other parts of the system may depend on.

### 4.1 Event families suitable for outbox

Examples:

- protocol events;
- pulse-plan events;
- reminder/adherence events;
- lab events;
- AI triage events;
- expert-case events;
- commercial/access events;
- catalog sync events where projections depend on them.

### 4.2 Event families not suitable for outbox

Examples:

- debug logs;
- handler trace logs;
- low-level internal timing noise;
- UI-only rendering events;
- ephemeral transport diagnostics with no business meaning.

---

## 5. What outbox protects

Outbox policy is designed to protect these system properties:

1. **No silent loss of important events**
2. **Retryability after downstream failure**
3. **Idempotent consumer behavior**
4. **Separation of transactional truth and asynchronous side effects**
5. **Controlled lag instead of hidden inconsistency**

---

## 6. Delivery model in CycleSync

### 6.1 Recommended model

CycleSync should use a durable outbox table (or equivalent durable event store) inside the main transactional persistence boundary.

### 6.2 Delivery flow

Conceptual flow:

1. transactional truth changes;
2. outbox record is written;
3. background dispatcher reads pending outbox rows;
4. dispatcher publishes event to internal consumers and/or queues;
5. delivery result is recorded;
6. retries happen if needed.

### 6.3 Why this fits CycleSync

Because CycleSync has multiple asynchronous derivative layers:

- search projection updates;
- analytics events;
- reminder-related summaries;
- protocol-health projections;
- AI-triage triggers;
- commercial metrics.

The outbox protects all of these from becoming fragile inline side effects.

---

## 7. Recommended outbox record model

An outbox event record should conceptually include:

- `outbox_event_id`
- `event_type`
- `aggregate_type`
- `aggregate_id`
- `payload_json`
- `status`
- `created_at`
- `published_at` (nullable)
- `retry_count`
- `last_error` (nullable)
- `next_attempt_at` (nullable)
- `correlation_id` (optional)
- `causation_id` (optional)

This document does not freeze the final SQL, but these semantics should remain stable.

---

## 8. Outbox statuses

Suggested outbox status set:

- `pending`
- `in_progress`
- `published`
- `failed_retryable`
- `failed_terminal`
- `dead_lettered` (optional later)

### 8.1 Status meaning

#### `pending`

The event exists and is waiting for delivery.

#### `in_progress`

A dispatcher is currently attempting delivery.

#### `published`

Delivery completed successfully for intended publish step.

#### `failed_retryable`

Delivery failed, but may be retried later.

#### `failed_terminal`

Delivery should no longer be retried automatically.

#### `dead_lettered`

Optional later state if the system formalizes dead-letter handling.

---

## 9. Delivery guarantees

### 9.1 Preferred delivery semantics

CycleSync should assume **at-least-once delivery** for outbox-published events.

### 9.2 Why at-least-once is acceptable

Because:

- exactly-once delivery is much harder and often overstated;
- projections and consumers can be made idempotent;
- CycleSync mostly needs reliable eventual downstream consistency, not magic transport purity.

### 9.3 Consequence

Every consumer must be written under the assumption that duplicate delivery is possible.

---

## 10. Idempotency requirements

Idempotency is mandatory for all consumers of outbox-driven events.

### 10.1 Why it matters

Because with retries and at-least-once delivery, duplicates will happen sooner or later.

### 10.2 Consumer rule

A consumer must be able to see the same event more than once without:

- duplicating projections;
- creating duplicate reminders;
- inflating analytics counters incorrectly;
- re-opening already processed states.

### 10.3 Typical idempotency strategies

Examples:

- remember processed event IDs;
- use upsert/merge logic;
- use unique keys on projection materialization;
- treat repeated event application as no-op.

---

## 11. Retry policy

### 11.1 Why retries exist

Consumers and transport layers fail.
Transient problems should not result in lost downstream meaning.

### 11.2 Retryable failure examples

- temporary queue outage;
- temporary projection storage unavailability;
- short-lived Meilisearch failure;
- transient worker/network issue.

### 11.3 Non-retryable failure examples

- malformed payload;
- unknown event contract version that cannot be interpreted;
- logically impossible consumer preconditions caused by code/schema mismatch.

### 11.4 Retry strategy principle

Retry policy should be bounded and backoff-based.
The system must not spin aggressively forever.

### 11.5 Suggested retry pattern

A practical policy may include:

- immediate or short-delay retry;
- exponential or stepped backoff;
- capped retry count;
- escalation to terminal/dead-letter state after exhaustion.

Exact intervals can remain operational policy, not domain truth.

---

## 12. Ordering and causality

### 12.1 Why ordering matters

Some downstream consumers depend on causal order.

Examples:

- `protocol_confirmed` before `protocol_activated`
- `pulse_plan_computed` before reminder scheduling
- `lab_report_completed` before `ai_assessment_created`

### 12.2 Practical rule

The system should preserve ordering where causal dependence is real, at least within the same aggregate or correlation chain where practical.

### 12.3 Important caution

Global total ordering across the whole system is not required and often not realistic.

Focus on:

- aggregate-level consistency;
- causal chain clarity;
- replay safety.

---

## 13. Consumer classes in CycleSync

Outbox-delivered events may be consumed by several consumer classes.

### 13.1 Projection consumers

Examples:

- search projection updater;
- adherence summary updater;
- protocol-health projector;
- analytics view projector;
- product health view updater.

### 13.2 Workflow consumers

Examples:

- AI-triage trigger;
- expert case context builder;
- commercial metric updater.

### 13.3 Notification consumers

Potential examples later:

- specialist-notify channel;
- owner/operator alerts;
- commercial or billing notifications if needed.

---

## 14. Reminder-specific caution

The outbox must not accidentally create duplicate reminder events or delivery loops.

### 14.1 Rule

Reminder scheduling consumers must be especially idempotent.

### 14.2 Why

Because duplicate reminder materialization is one of the easiest ways to destroy user trust.

### 14.3 Practical expectation

If `pulse_plan_computed` or related events are replayed, reminder generation must:

- detect that reminder rows already exist for the relevant plan state; or
- supersede old ones cleanly;
- never blindly duplicate execution cards.

---

## 15. Analytics-specific caution

Analytics consumers must avoid counting duplicates as new truth.

### 15.1 Rule

Analytics ingestion should treat each event ID as immutable and unique.

### 15.2 Consequence

If an already-seen event is replayed, the analytics layer must not double-count it.

### 15.3 Why this matters

Because duplicate commercial, reminder or adherence counts will quietly poison every health view and business decision downstream.

---

## 16. Search projection-specific caution

Search projections are rebuildable and can tolerate asynchronous updates, but they must still remain coherent.

### 16.1 Rule

Catalog change events should update only affected search documents where possible.

### 16.2 Full rebuild rule

If search schema/normalization changes materially, full rebuild is preferred over clever incremental patching.

### 16.3 Why

Because broken search is a visible product failure in a search-first system.

---

## 17. Delivery lag visibility

### 17.1 Why visibility matters

Outbox backlog or failing consumers can silently make the product inconsistent even while transactional writes continue.

### 17.2 Minimum visibility needs

The system should make it possible to know:

- how many outbox events are pending;
- how many are retrying;
- oldest pending event age;
- terminal/dead-letter counts;
- consumer lag where relevant.

### 17.3 Product implication

This is not just DevOps vanity.
Severe lag affects:

- search freshness;
- health views;
- analytics trust;
- specialist context freshness.

---

## 18. Dead-letter / terminal failure policy

### 18.1 Why dead-letter handling matters

Some events will fail repeatedly and should not block the queue forever.

### 18.2 Terminal handling rule

When retries are exhausted or the failure is non-retryable:

- mark the event as terminal or dead-lettered;
- preserve payload and error context;
- make it visible for operator intervention.

### 18.3 Important rule

Dead-letter is not “delete and forget”.
It is “preserve the failed fact and expose it for repair”.

---

## 19. Replay policy

### 19.1 Why replay exists

Replay is needed when:

- a consumer was down;
- projection schema changed;
- analytics definitions changed;
- data repair is required.

### 19.2 Replay rule

Replay must be safe because:

- consumers are idempotent;
- outbox events are immutable;
- projection rebuild logic exists.

### 19.3 Replay caution

Replay should be scoped where possible.
Do not replay the entire universe if a targeted window or aggregate subset is sufficient.

---

## 20. Operational scenarios

### 20.1 Scenario: search updater outage

Effect:

- catalog writes continue;
- search projections lag.

Policy:

- pending outbox events accumulate;
- search updater recovers and replays;
- search freshness catches up.

### 20.2 Scenario: analytics projector bug fixed

Policy:

- replay affected event window;
- rebuild metrics safely from immutable raw facts/events.

### 20.3 Scenario: reminder summary drift detected

Policy:

- use targeted rebuild for affected protocol/user scope;
- do not mutate source reminder/adherence truth.

### 20.4 Scenario: repeated malformed payloads

Policy:

- fail terminal/dead-letter;
- expose for manual/code-level resolution;
- prevent infinite retry loops.

---

## 21. Guardrails

The outbox and delivery layer must avoid the following mistakes.

### 21.1 Inline side-effect fragility

Do not depend purely on synchronous inline side effects for downstream truth.

### 21.2 Duplicate side-effect blindness

Do not assume events are delivered exactly once.

### 21.3 Retry-without-bounds

Do not retry forever with no backoff and no terminal handling.

### 21.4 Lost terminal failures

Do not hide dead-letter/terminal failures from operational visibility.

### 21.5 Transport-driven semantics

Do not let queue implementation details redefine business event meaning.

### 21.6 Outbox as analytics dump

Do not stuff every technical curiosity into outbox just because it is available.

---

## 22. Relationship to other docs

This document depends on and supports:

- `71_event_catalog.md`
- `74_projection_rebuild_rules.md`
- `70_analytics.md`
- search, reminder, adherence and expert-case documents.

It acts as the delivery-policy spine between domain facts and downstream derived behavior.

---

## 23. Final statement

CycleSync needs an outbox and delivery policy because the product depends on many asynchronous consequences of core state changes.

The correct rule is simple:

- commit truth;
- persist event;
- deliver asynchronously;
- retry safely;
- keep consumers idempotent;
- expose lag and terminal failures.

If this layer is weak, projections, analytics and health views will drift into contradiction.  
If it is strong, the system can scale its derived layers without corrupting trust.
