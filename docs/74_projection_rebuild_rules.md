# CycleSync Projection Rebuild Rules

> Projection rebuild, resync and consistency rules document for **CycleSync**.

---

## 1. Purpose of this document

This document defines how derived projections in CycleSync are built, refreshed, repaired and fully rebuilt.

Its goals are to:

- define what counts as a projection in CycleSync;
- distinguish transactional truth from derived views;
- describe rebuild triggers and rebuild modes;
- define consistency expectations and acceptable lag;
- prevent search, analytics, health views and summaries from drifting into conflicting pseudo-truths;
- establish operational rules for reindexing and projection repair.

This document is **not**:

- a low-level worker implementation spec;
- a SQL migration document;
- a queue transport document;
- a DevOps runbook in full detail.

Those should be specified separately later if needed.

---

## 2. Why this document exists

CycleSync depends on multiple derived layers:

- compound search documents;
- user search documents later;
- adherence summaries;
- analytics projections;
- product health views;
- specialist summary views later.

All of these are useful, but none of them are the primary truth.

Without formal rebuild rules, the system will eventually suffer from:

- stale search results;
- mismatched reminder/adherence summaries;
- analytics lying by lag or duplication;
- health views showing a different reality than operational state;
- operators losing trust in the product.

This document exists to stop that early.

---

## 3. Core projection principle

The central rule is:

> **Transactional truth is authoritative. Projections are disposable and rebuildable.**

That means:

- projections may lag;
- projections may be wrong temporarily;
- projections may be dropped and rebuilt;
- projections must never become the only trusted version of domain state.

---

## 4. What counts as a projection in CycleSync

In CycleSync, a projection is any read-optimized, derived representation built from transactional truth and/or event history.

### 4.1 Main projection families

1. **Search projections**
   - compound search documents
   - user search documents later

2. **Reminder / adherence summaries**
   - adherence snapshots
   - protocol health states

3. **Analytics projections**
   - metric summaries
   - funnel summaries
   - reminder/adherence summaries
   - commercial summaries

4. **Product health views**
   - search health
   - activation funnel health
   - pulse engine health
   - reminder delivery health
   - protocol integrity health
   - monitoring health
   - specialist health
   - commercial health

5. **Specialist convenience views**
   - case summaries
   - protocol snapshots
   - recent lab/high-risk rollups later

### 4.2 What is not a projection

These are not projections and must remain authoritative:

- compound catalog tables;
- user registry tables;
- protocols;
- pulse plans;
- reminders;
- adherence actions;
- lab reports;
- AI assessments;
- expert case records.

---

## 5. Projection categories by consistency needs

Not all projections have the same urgency.

### 5.1 Tier A projections — near-operational importance

Examples:

- compound search documents;
- active adherence summary;
- protocol health state.

These should be updated quickly and kept reasonably fresh because they affect user-facing and specialist-facing flows.

### 5.2 Tier B projections — operational insight layer

Examples:

- reminder/adherence rollups;
- specialist case summaries;
- recent protocol summaries.

These can tolerate some lag but should stay trustworthy.

### 5.3 Tier C projections — management / analytics layer

Examples:

- daily metrics;
- commercial summaries;
- product health views;
- funnel reports.

These can lag more without breaking product operation.

---

## 6. Acceptable consistency model

### 6.1 Transactional core

The transactional core should be treated as strongly authoritative inside normal database semantics.

### 6.2 Projections

Projections are allowed to be **eventually consistent**.

### 6.3 Important rule

Eventual consistency is acceptable only if:

- lag is visible/understood;
- rebuild is possible;
- projections do not silently contradict transactional truth for long periods;
- user-critical flows have safe fallbacks where needed.

---

## 7. Rebuild modes

CycleSync should support multiple rebuild modes.

## 7.1 Incremental update

The normal mode.

Used when:

- one compound changed;
- one protocol changed;
- one reminder/adherence event occurred;
- one lab report was added.

Goal:

- update only affected projections.

## 7.2 Batch catch-up rebuild

Used when:

- a queue lagged;
- an outage occurred;
- many events accumulated;
- projections need replay over a bounded time window.

Goal:

- recover consistency without full global rebuild.

## 7.3 Full rebuild

Used when:

- projection schema changed materially;
- search document design changed;
- analytics definitions changed;
- corruption or severe drift occurred.

Goal:

- recompute projection truth from source records and/or events.

## 7.4 Targeted repair rebuild

Used when:

- one protocol summary looks wrong;
- one compound search document is broken;
- one expert case summary drifted;
- one user’s adherence summary needs recomputation.

Goal:

- repair a narrow projection scope without touching the world.

---

## 8. Projection sources

Different projection families derive from different source layers.

### 8.1 Search projections

Primary sources:

- compound catalog tables;
- aliases;
- composition entries;
- brand/substance/ester normalization.

### 8.2 Adherence and protocol-health projections

Primary sources:

- protocols;
- pulse plans;
- reminder events;
- adherence actions.

### 8.3 Analytics projections

Primary sources:

- normalized analytics events;
- some transactional snapshots where justified.

### 8.4 Product-health views

Primary sources:

- analytics projections;
- selected transactional truth references;
- adherence/protocol-health summaries.

### 8.5 Specialist summary projections later

Primary sources:

- protocol truth;
- pulse-plan truth;
- adherence truth;
- labs;
- AI assessments;
- expert-case records.

---

## 9. Trigger model for projection updates

Projection updates should be triggered by meaningful domain/application events.

### 9.1 Example trigger patterns

- `compound_catalog_synced` -> rebuild affected compound search docs
- `compound_updated` -> rebuild compound search doc
- `protocol_confirmed` -> create/update protocol summary projections
- `pulse_plan_computed` -> update protocol execution summaries
- `reminder_done` / `reminder_skipped` / `adherence_missed` -> update adherence and protocol-health projections
- `lab_report_completed` -> update monitoring-related projections
- `ai_assessment_created` -> update monitoring and escalation views
- `consultation_paid` -> update commercial projections

### 9.2 Important rule

One event may update multiple projections, but the projection consumers must remain independent.

---

## 10. Search projection rebuild rules

### 10.1 Search projection nature

Compound search docs are critical, but still derived.

### 10.2 Rebuild triggers

Rebuild affected search documents when any of the following changes:

- compound created/updated;
- brand created/updated;
- alias added/removed/changed;
- substance/ester linkage changed;
- composition entry changed;
- catalog sync completed.

### 10.3 Full search rebuild triggers

Run a full search rebuild when:

- Meilisearch document structure changes;
- normalization rules materially change;
- search ranking fields change significantly;
- a bulk catalog resync invalidates old index assumptions.

### 10.4 Fallback rule

If search projection is stale or unavailable, the transactional catalog should still allow reduced lookup.

---

## 11. Adherence and protocol-health projection rebuild rules

### 11.1 Why these projections matter

These projections influence one of the strongest product promises: whether a protocol is still being followed.

### 11.2 Rebuild triggers

Update affected adherence/protocol-health summaries when:

- reminder event created;
- reminder expired;
- reminder cleaned;
- adherence action created;
- protocol activated/paused/completed/cancelled;
- pulse plan superseded.

### 11.3 Broken-state sensitivity

Because protocol-health projections may drive visible product states such as `degrading` or `broken`, targeted repair must be available.

### 11.4 Rebuild rule

If protocol-health projection is suspected to be wrong, it must be recomputable from:

- protocol state;
- pulse-plan linkage;
- reminder history;
- adherence history.

---

## 12. Analytics projection rebuild rules

### 12.1 Analytics raw vs analytics views

Raw analytics events should remain append-only where possible.
Derived analytics views should be rebuildable from raw events.

### 12.2 Rebuild triggers

Rebuild or recompute analytics views when:

- event definitions changed materially;
- projection formulas changed;
- event ingestion lag or failure caused partial summaries;
- a historical backfill is needed.

### 12.3 Time-window rebuild pattern

Analytics rebuilds should support bounded windows such as:

- one day;
- rolling 7 days;
- rolling 30 days;
- custom date ranges.

This avoids unnecessarily rebuilding everything.

---

## 13. Product health view rebuild rules

### 13.1 Health views are second-order projections

Product-health views are built on top of analytics and some operational summaries.
They are not first-order transactional derivatives.

### 13.2 Rebuild triggers

Health views should refresh when:

- upstream analytics projections refresh;
- adherence/protocol-health projections change;
- major commercial view changes occur;
- search health counters change materially.

### 13.3 Important rule

Because health views are summary-of-summary structures, the system must avoid hiding lag. Freshness or as-of timestamps are recommended.

---

## 14. Specialist summary projection rebuild rules

This may be a later layer, but the rules should be clear now.

### 14.1 Rebuild triggers

Refresh specialist summary projections when:

- protocol changed;
- pulse plan changed;
- adherence changed;
- lab report added/updated;
- AI assessment created;
- expert case state/message changed.

### 14.2 Rebuild scope

These rebuilds should be highly targeted per user/case rather than global.

---

## 15. Outbox and idempotency requirements

Projection rebuild depends on reliable event propagation.

### 15.1 Outbox compatibility

If an outbox pattern is used, projection consumers should read from reliable event delivery rather than fragile inline side effects.

### 15.2 Idempotency rule

All projection consumers must be idempotent.
Repeated delivery of the same event must not create duplicate or corrupted projections.

### 15.3 Retry rule

Projection failures must be retryable without requiring manual data surgery.

---

## 16. Projection freshness and lag visibility

### 16.1 Freshness must be observable

For important projection families, the system should know:

- when a projection was last updated;
- whether it is current;
- whether rebuild is pending or failed.

### 16.2 Why lag visibility matters

Because a projection may be technically present but operationally stale.
Without visibility, stale summaries silently destroy trust.

### 16.3 Suggested freshness metadata

Where useful, projections may include:

- `indexed_at`
- `computed_at`
- `source_window_end`
- `projection_version`

---

## 17. Rebuild safety rules

### 17.1 Never rebuild by mutating transactional truth

Projection rebuild must never “fix” source data by silently modifying transactional truth.

### 17.2 Never delete source truth because projection is stale

The correct response to stale projections is rebuild, not destructive cleanup of transactional data.

### 17.3 Projection schema changes require version awareness

If the structure of a projection materially changes, the rebuild process must understand projection versioning.

---

## 18. Operational rebuild scenarios

### 18.1 Scenario: catalog alias update

Action:

- rebuild affected compound search docs only.

### 18.2 Scenario: pulse-plan superseded

Action:

- rebuild protocol summary projections;
- rebuild active adherence/protocol-health projections;
- reschedule/refresh reminder-linked views where needed.

### 18.3 Scenario: backlog in reminder/adherence processing

Action:

- batch catch-up affected adherence summaries;
- recompute protocol-health state for affected protocols.

### 18.4 Scenario: analytics formula changed

Action:

- rebuild analytics projections over relevant windows;
- refresh product health views derived from them.

### 18.5 Scenario: Meilisearch index corruption

Action:

- full search projection rebuild from compound catalog truth.

---

## 19. Priority order for projection recovery

If multiple projection layers are broken, recovery should follow a disciplined order.

Recommended order:

1. restore transactional truth access
2. rebuild search projections
3. rebuild protocol/adherence summaries
4. rebuild analytics raw ingestion consistency
5. rebuild analytics views
6. rebuild product-health views
7. rebuild specialist convenience views

This order reflects how downstream views depend on upstream truth.

---

## 20. Guardrails

The projection layer must avoid the following mistakes.

### 20.1 Projection-as-truth

Do not let operators trust projections over the source records when conflict exists.

### 20.2 Silent drift

Do not allow projections to remain stale without freshness visibility.

### 20.3 Full rebuild addiction

Do not solve every inconsistency with global rebuilds if targeted repair is possible.

### 20.4 Non-idempotent rebuilds

Do not build projection workers that duplicate or distort state on retries.

### 20.5 UI assumptions leaking into rebuild logic

Do not let chat message behavior define projection correctness.

### 20.6 Health-view recursion confusion

Do not forget that product-health views are second-order projections and can be wrong if upstream layers drift.

---

## 21. Recommended future dependent documents

This document should feed the creation of:

- `docs/75_specialist_operational_metrics.md`
- `docs/76_outbox_and_delivery_policy.md`
- `docs/77_projection_freshness_monitoring.md`
- `docs/78_search_reindex_runbook.md`

These names are recommendations and may change.

---

## 22. Final statement

CycleSync relies on multiple powerful derived layers, but all of them must remain subordinate to transactional truth.

Search, adherence summaries, analytics and product-health views are valuable only if they are:

- rebuildable;
- freshness-aware;
- idempotent;
- transparently derived;
- operationally repairable.

This document defines how CycleSync prevents its derived layers from turning into a contradictory swamp of half-true screens and stale counters.
