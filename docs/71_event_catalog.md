# CycleSync Event Catalog

> Event catalog document for **CycleSync**.

---

## 1. Purpose of this document

This document defines the event catalog of CycleSync.

Its goals are to:

- establish a stable event vocabulary across the system;
- define which events matter for analytics, projections, reminders, AI triage and commercial logic;
- separate domain events from delivery/logging noise;
- describe event payload expectations at a high level;
- support future event-driven architecture, outbox processing, analytics and projection rebuilds.

This document is **not**:

- a transport-level queue spec;
- a Kafka/Rabbit/etc. binding spec;
- a monitoring log catalog;
- a full JSON schema registry.

Those should be specified separately later.

---

## 2. Why an event catalog is necessary

CycleSync already has multiple event-producing domains:

- search;
- draft/protocol creation;
- pulse-engine computation;
- reminders;
- adherence;
- labs;
- AI triage;
- expert cases;
- commercial access and payments.

Without a formal catalog, the system will drift into:

- duplicated event names;
- inconsistent payload meaning;
- broken analytics;
- projection confusion;
- weak auditability.

The event catalog exists to stop that rot early.

---

## 3. Event design principles

### 3.1 Event names must reflect business meaning

Events should express meaningful product/domain state changes, not low-level code accidents.

Good:

- `protocol_confirmed`
- `pulse_plan_computed`
- `reminder_snoozed`

Bad:

- `handler_finished_ok`
- `db_update_success`
- `bot_step_3_done`

### 3.2 Events are immutable facts

An event describes something that happened.
It must not be edited into a different meaning later.

### 3.3 Domain truth first, projections later

Events should usually be emitted from domain/application truth, not from projection layers.

### 3.4 Stable vocabulary

Once an event family is in use, renaming or semantic drift must be carefully controlled.

### 3.5 Enough context, not payload bloat

An event should carry enough context to be useful, but not become a giant data dump.

### 3.6 Transport is secondary

The event catalog defines semantic contracts first.
How the event is transported is a separate infrastructure concern.

---

## 4. Event layers

CycleSync events should be understood across three layers.

### 4.1 Domain events

Meaningful business/domain facts such as:

- protocol confirmed;
- pulse plan computed;
- reminder skipped;
- lab report created.

### 4.2 Application/integration events

Events used to coordinate cross-context behavior or external integrations.

Examples:

- trigger reminder generation;
- trigger search projection rebuild;
- trigger analytics ingestion;
- notify specialist case assembly.

### 4.3 Technical events/logging

Transport retries, worker heartbeats, handler debug messages and similar noise are **not** part of this catalog unless they represent meaningful business state.

---

## 5. Event naming convention

Recommended naming style:

- lowercase snake_case;
- past-tense semantic fact;
- family prefix by domain if useful.

Examples:

- `search_executed`
- `draft_created`
- `protocol_confirmed`
- `pulse_plan_computed`
- `reminder_sent`
- `adherence_done`
- `lab_report_created`
- `ai_assessment_created`
- `expert_case_opened`
- `execution_tier_purchased`

### 5.1 Important rule

Events must be named by **what happened**, not by who happened to trigger it.

---

## 6. Common event envelope (conceptual)

Every event should conceptually carry a shared envelope.

Recommended common fields:

- `event_id`
- `event_type`
- `occurred_at`
- `entity_type`
- `entity_id`
- `source_context`
- `payload`
- `correlation_id` (optional but recommended)
- `causation_id` (optional later)
- `actor_type` (user/system/specialist/admin etc. where relevant)
- `actor_id` (optional)

This document does not freeze a final JSON contract, but the semantics should remain stable.

---

## 7. Search events

Search is the front door of CycleSync and must be heavily instrumented.

### 7.1 Core search events

#### `search_executed`

Fires when a search request is run.

Suggested payload elements:

- query_text
- normalized_query
- source (`text` / `voice`)
- result_count
- search_intent_class (if known)

#### `search_zero_result`

Fires when a search returns no results.

#### `search_result_opened`

Fires when the user opens a compound card from results.

#### `search_result_added_to_draft`

Fires when a result is added into calculation draft.

#### `voice_search_executed`

Fires when a voice input was converted into a search action.

#### `search_not_found_logged`

Fires when a no-result query is stored for future catalog enrichment.

---

## 8. Draft events

Draft is the bridge between search and protocol.

### 8.1 Core draft events

#### `draft_created`

A calculation draft context has been created.

#### `compound_added_to_draft`

A concrete `compound_id` has been added to the draft.

#### `compound_removed_from_draft`

A selected compound was removed from draft.

#### `draft_reordered`

Draft compound order changed if ordering matters.

#### `draft_weekly_target_set`

The weekly target was defined or changed.

#### `draft_duration_set`

Duration was defined or changed.

#### `draft_preset_selected`

The user selected or changed a preset.

#### `draft_constraint_changed`

Volume/frequency or similar constraint changed.

#### `draft_cleared`

The draft was intentionally reset.

---

## 9. Protocol events

### 9.1 Core protocol events

#### `protocol_created`

A protocol object was created from draft context.

#### `protocol_updated`

Material protocol data changed.

#### `protocol_calculation_requested`

The user/system requested pulse-plan calculation.

#### `protocol_calculated`

Calculation completed successfully and a candidate/current pulse plan exists.

#### `protocol_confirmed`

The user confirmed the computed protocol plan.

#### `protocol_scheduled`

A confirmed protocol is waiting for future start date.

#### `protocol_activated`

Execution of the protocol became active.

#### `protocol_paused`

The protocol was paused.

#### `protocol_completed`

The protocol reached completion.

#### `protocol_cancelled`

The protocol was abandoned/cancelled.

#### `protocol_archived`

The protocol was archived.

#### `protocol_broken`

The system concluded that execution discipline collapsed and the active plan can no longer be trusted.

#### `protocol_deactivated_due_to_discipline`

Reminder/execution automation was shut down because protocol health fell below threshold.

---

## 10. Pulse Engine events

### 10.1 Core engine events

#### `pulse_plan_computation_started`

Optional but useful for timing/observability.

#### `pulse_plan_computed`

A pulse plan was successfully generated.

Suggested payload elements:

- protocol_id
- preset_code
- algorithm_version
- window_days
- flatness_score (if available)
- warning_count

#### `pulse_plan_failed`

Calculation failed.

Suggested payload elements:

- failure_reason
- protocol_id
- preset_code

#### `pulse_plan_warning_emitted`

A plan was generated but with non-trivial warnings/trade-offs.

#### `pulse_plan_superseded`

A newer pulse plan replaced a previous one.

---

## 11. Reminder events

### 11.1 Core reminder events

#### `reminder_scheduled`

A reminder event was created from pulse-plan or related monitoring flow.

#### `reminder_sent`

A reminder message was successfully sent.

#### `reminder_delivery_failed`

A send attempt failed.

#### `reminder_snoozed`

The user explicitly snoozed the reminder.

#### `reminder_skipped`

The user explicitly skipped the scheduled action.

#### `reminder_expired`

A reminder passed its useful action window.

#### `reminder_cleaned_from_chat`

A stale/obsolete reminder message was edited or deleted for chat hygiene.

#### `reminders_enabled`

The user enabled reminder system.

#### `reminders_disabled`

The user disabled reminder system.

---

## 12. Adherence events

Adherence events represent what actually happened at execution level.

### 12.1 Core adherence events

#### `adherence_done`

The user confirmed completion.

#### `adherence_snoozed`

The user delayed action.

#### `adherence_skipped`

The user explicitly skipped execution.

#### `adherence_missed`

No valid action was recorded and the event became a negative adherence signal.

#### `adherence_snapshot_computed`

A summary snapshot or score was derived.

#### `protocol_health_degraded`

A derived health-state deterioration threshold was crossed.

#### `protocol_health_broken`

The protocol reached a broken state.

---

## 13. Lab events

### 13.1 Core lab events

#### `lab_report_created`

A structured lab report object was created.

#### `lab_marker_added`

A structured marker was added to a report.

#### `lab_report_completed`

The user finished entering a report.

#### `lab_report_updated`

A report was materially edited.

#### `lab_attachment_uploaded`

A raw attachment was uploaded (optional/secondary flow).

#### `lab_panel_selected`

A known panel template was chosen.

---

## 14. AI triage events

### 14.1 Core AI events

#### `ai_assessment_requested`

An AI triage run was initiated.

#### `ai_assessment_created`

AI generated a preliminary structured assessment.

#### `ai_risk_flag_emitted`

A risk flag was generated.

#### `ai_trend_observation_created`

A historical comparison/trend observation was created.

#### `ai_escalation_suggested`

AI recommended escalation to a specialist.

#### `ai_assessment_opened`

The user opened the AI result view.

---

## 15. Expert case events

### 15.1 Core expert events

#### `expert_case_opened`

A specialist case was created.

#### `expert_case_context_assembled`

Case context package was generated from protocol/adherence/labs/AI data.

#### `expert_case_first_reply_sent`

The first specialist reply was sent.

#### `expert_case_follow_up_requested`

A follow-up action or response is expected.

#### `expert_case_closed`

The case was closed.

---

## 16. Commercial and access events

These events support monetization and feature-gating analytics.

### 16.1 Core commercial events

#### `access_key_redeemed`

A user activated access through a key.

#### `free_limit_reached`

A user hit a defined free-tier limit.

#### `paywall_seen`

The product showed a paywall at a feature or action boundary.

#### `execution_tier_purchased`

A paid execution/reminder-related entitlement was purchased.

#### `reminders_access_enabled`

Commercial access to reminder functionality became active.

#### `consultation_checkout_started`

A paid specialist flow checkout started.

#### `consultation_paid`

A paid specialist case/consultation was successfully paid.

#### `entitlement_granted`

An access entitlement was granted.

#### `entitlement_expired`

An entitlement ended.

---

## 17. Catalog growth and maintenance events

### 17.1 Core catalog-growth events

#### `catalog_sync_started`

A sync run from source data began.

#### `catalog_sync_completed`

Catalog sync completed.

#### `catalog_sync_failed`

Catalog sync failed.

#### `catalog_item_created`

A new compound/brand/substance item was added.

#### `catalog_item_updated`

A catalog item was materially updated.

#### `catalog_alias_added`

Search alias enrichment occurred.

#### `catalog_item_added_after_demand`

A new item was added in response to repeated not-found demand.

---

## 18. Event payload guidelines by family

### 18.1 Search family payloads should usually include

- query_text
- normalized_query
- source
- result_count
- optional top_hit_compound_id

### 18.2 Protocol/pulse family payloads should usually include

- protocol_id
- preset_code
- pulse_plan_id where relevant
- status or transition info
- warning/failure code where relevant

### 18.3 Reminder/adherence family payloads should usually include

- user_id
- protocol_id
- reminder_event_id
- pulse_plan_line_id where relevant
- action_type or state

### 18.4 Lab/AI/expert payloads should usually include

- user_id
- lab_report_id / ai_assessment_id / expert_case_id
- protocol_id if contextually linked
- severity or escalation flag where relevant

### 18.5 Commercial payloads should usually include

- user_id
- plan/entitlement identifier
- feature gate identifier
- commercial context (trial, execution tier, consultation, etc.)

---

## 19. Event consumers

Different parts of the system may consume these events.

### 19.1 Likely consumers

- analytics ingestion;
- search projection updater;
- reminder scheduler;
- adherence summarizer;
- broken-protocol evaluator;
- AI triage pipeline;
- expert case context builder;
- commercial metrics projections.

### 19.2 Important rule

Core flows must not hardcode every downstream reaction inline.

Instead:

- emit event;
- let projections/consumers react.

---

## 20. Event quality rules

### 20.1 One event, one meaning

Do not overload one event with multiple incompatible meanings.

### 20.2 Do not emit projections as domain facts

For example:

- `adherence_score_updated` may be acceptable as a derived analytics/projection event,
- but it must not replace real adherence events like `adherence_done` or `adherence_missed`.

### 20.3 Avoid duplicate semantic events

Do not create both:

- `reminder_done`
- `user_completed_reminder`

if they mean the same business fact.

Choose one stable vocabulary.

---

## 21. Specialist case lifecycle events (MVP loop)

For Wave 7 specialist loop, the following events are required as lifecycle truth:

- `specialist_case_taken_in_review`
- `specialist_case_response_created`
- `specialist_case_answered`
- `specialist_case_closed`

These events should be emitted from application service transitions, not from Telegram UI handlers.

---

## 22. Event ordering and causality

The system should preserve causal relationships where possible.

Examples:

- `protocol_confirmed` -> `pulse_plan_computed` -> `reminder_scheduled`
- `lab_report_completed` -> `ai_assessment_requested` -> `ai_assessment_created`
- `ai_escalation_suggested` -> `consultation_checkout_started` -> `consultation_paid` -> `expert_case_opened`

This does not require strict synchronous processing, but the semantic chain must remain understandable.

---

## 23. Event catalog guardrails

The event catalog must avoid the following mistakes.

### 22.1 Debug-log pollution

Do not let technical noise pollute business event vocabulary.

### 22.2 UI-driven naming

Do not define event names by Telegram button text.

### 22.3 Semantic drift

Do not quietly change event meaning over time while keeping the same event name.

### 22.4 Analytics-only events without source truth

Do not invent “business events” only for dashboard vanity if they do not reflect real product state.

### 22.5 Cross-domain confusion
n
Do not use protocol events to describe reminder facts or reminder events to describe adherence facts.

---

## 24. Recommended future dependent documents

This event catalog should feed the creation of:

- `docs/72_product_health_views.md`
- `docs/73_commercial_metrics.md`
- `docs/74_projection_rebuild_rules.md`
- `docs/75_specialist_operational_metrics.md`
- `docs/76_outbox_and_delivery_policy.md`

These names are recommendations and may change.

---

## 25. Final statement

CycleSync needs a stable event vocabulary because the product already spans:

- search;
- draft;
- protocols;
- pulse-engine;
- reminders;
- adherence;
- labs;
- AI triage;
- expert cases;
- commercial access.

Without a formal catalog, analytics, projections and cross-context behavior will drift into inconsistency.

This document defines the semantic event spine of the system.
