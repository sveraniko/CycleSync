# CycleSync Analytics

> Analytics and product-insight document for **CycleSync**.

---

## 1. Purpose of this document

This document defines the analytics layer of CycleSync.

Its goals are to:

- identify the key events the product must capture;
- define analytics domains and projection groups;
- formalize how analytics reflects product truth;
- support operational insight, product iteration and commercial decisions;
- ensure analytics is built from day one rather than bolted on later.

This document is **not**:

- a BI dashboard design document;
- a SQL-only metric catalog;
- a marketing strategy file;
- a final payment/funnel implementation plan.

Those should be specified separately later.

---

## 2. Why analytics matters in CycleSync

CycleSync is not just a calculator.
It is a system that depends on:

- search quality;
- protocol creation quality;
- pulse-plan adoption;
- reminder response behavior;
- adherence discipline;
- lab monitoring behavior;
- escalation to specialists.

Without analytics, the product would be blind to:

- where users drop out;
- whether search works;
- whether reminders are useful;
- whether broken-protocol logic is firing too often;
- whether specialist escalation is used appropriately;
- which features users are willing to pay for later.

---

## 3. Analytics design principles

### 3.1 Event-first analytics

Analytics should be built from meaningful domain/application events, not from random handler logs.

### 3.2 Product-truth alignment

Analytics must reflect the real product spine:

- search;
- draft;
- protocol;
- pulse plan;
- reminders;
- adherence;
- labs;
- AI triage;
- expert cases.

### 3.3 Derived, not transactional

Analytics is a derived layer.
It must not be used as the primary source of protocol truth.

### 3.4 Rebuildability

Where possible, analytics projections should be rebuildable from event history.

### 3.5 Commercial usefulness

Analytics should help answer not only “what happened” but also:

- what users value;
- what they repeat;
- what they ignore;
- what they will plausibly pay for.

---

## 4. Main analytics domains

CycleSync analytics should be organized into these domains:

1. Search analytics
2. Draft/protocol funnel analytics
3. Pulse-plan analytics
4. Reminder analytics
5. Adherence analytics
6. Labs analytics
7. AI triage analytics
8. Expert case analytics
9. Commercial/funnel analytics (later or in parallel)
10. Catalog growth analytics

---

## 5. Search analytics

### 5.1 Why it matters

CycleSync is search-first. Search quality is product quality.

### 5.2 Core metrics

- total search queries;
- text vs voice query share;
- zero-result rate;
- one-result exact match rate;
- multi-result query rate;
- `Open` from result rate;
- `+Draft` from result rate;
- top not-found query clusters;
- brand alias mismatch frequency;
- composition/dosage query success rate.

### 5.3 Core events

Examples:

- `search_executed`
- `search_zero_result`
- `search_result_opened`
- `search_result_added_to_draft`
- `voice_search_executed`

---

## 6. Draft and protocol funnel analytics

### 6.1 Why it matters

This is the first true activation funnel of the product.

### 6.2 Funnel stages

- search performed
- first compound added to draft
- second/third compound added
- weekly target entered
- duration entered
- preset selected
- calculation requested
- pulse-plan generated
- protocol confirmed
- protocol activated

### 6.3 Core metrics

- search-to-draft conversion;
- draft-to-calculation conversion;
- calculation-to-confirmation conversion;
- confirmation-to-activation conversion;
- drop-off by stage;
- average draft size;
- most selected preset;
- time from first search to first confirmed protocol.

### 6.4 Core events

Examples:

- `draft_created`
- `compound_added_to_draft`
- `draft_weekly_target_set`
- `draft_duration_set`
- `draft_preset_selected`
- `protocol_calculation_requested`
- `protocol_calculated`
- `protocol_confirmed`
- `protocol_activated`

---

## 7. Pulse-plan analytics

### 7.1 Why it matters

The pulse engine is the heart of the product. Its output must be measurable.

### 7.2 Core metrics

- pulse plans generated;
- plan generation success rate;
- infeasible calculation rate;
- per-preset usage share;
- per-preset warning rate;
- average schedule complexity;
- average volume conflict rate;
- average recomputation rate.

### 7.3 Core events

Examples:

- `pulse_plan_computed`
- `pulse_plan_failed`
- `pulse_plan_warning_emitted`
- `pulse_plan_superseded`

---

## 8. Reminder analytics

### 8.1 Why it matters

Reminder quality determines whether the pulse plan survives contact with reality.

### 8.2 Core metrics

- reminders scheduled;
- reminders sent;
- reminders successfully delivered;
- user response rate;
- snooze rate;
- retry rate;
- expired reminder rate;
- deleted/cleaned stale reminder rate;
- reminders disabled rate.

### 8.3 Core events

Examples:

- `reminder_scheduled`
- `reminder_sent`
- `reminder_delivery_failed`
- `reminder_snoozed`
- `reminder_skipped`
- `reminder_expired`
- `reminders_disabled`
- `reminders_enabled`

---

## 9. Adherence analytics

### 9.1 Why it matters

Adherence is one of the core differentiators of CycleSync.

### 9.2 Core metrics

- done rate;
- skip rate;
- non-response rate;
- time-to-response;
- adherence score distribution;
- broken-protocol rate;
- average time to broken state;
- adherence by preset;
- adherence by reminder setting state.

### 9.3 Core events

Examples:

- `adherence_done`
- `adherence_skip`
- `adherence_missed`
- `protocol_broken`
- `protocol_deactivated_due_to_discipline`

---

## 10. Labs analytics

### 10.1 Why it matters

Labs are the main observation layer of the product.

### 10.2 Core metrics

- number of lab reports entered;
- average markers per report;
- panel usage by type;
- days from protocol activation to first lab report;
- repeat lab submission rate;
- incomplete report rate;
- use of custom reference ranges.

### 10.3 Core events

Examples:

- `lab_report_created`
- `lab_marker_added`
- `lab_report_completed`
- `lab_panel_selected`

---

## 11. AI triage analytics

### 11.1 Why it matters

AI is not the core product, but it must justify its existence.

### 11.2 Core metrics

- AI assessments generated;
- average time from lab entry to AI assessment;
- risk-flag distribution;
- escalation recommendation rate;
- cases where AI output was not opened or ignored;
- agreement/disagreement signals later if specialist comparison is added.

### 11.3 Core events

Examples:

- `ai_assessment_created`
- `ai_risk_flag_emitted`
- `ai_escalation_suggested`
- `ai_summary_opened`

---

## 12. Expert case analytics

### 12.1 Why it matters

This is the human-premium and trust layer of the system.

### 12.2 Core metrics

- expert cases opened;
- time from AI triage to expert case;
- time from case open to first specialist reply;
- case closure rate;
- average case duration;
- specialist workload later;
- percentage of active protocols that escalate.

### 12.3 Core events

Examples:

- `expert_case_opened`
- `expert_case_first_reply_sent`
- `expert_case_follow_up_requested`
- `expert_case_closed`

---

## 13. Catalog growth analytics

### 13.1 Why it matters

Because in a search-first system, not-found requests are product development signals.

### 13.2 Core metrics

- top zero-result query clusters;
- repeated not-found substances;
- repeated not-found brands;
- repeated not-found product combinations;
- search demand by composition token;
- delta after alias/catalog updates.

### 13.3 Core events

Examples:

- `catalog_search_not_found_logged`
- `catalog_item_added_after_demand`
- `catalog_alias_added`

---

## 14. Commercial analytics

This domain may start lightweight, but the model should be ready from the beginning.

### 14.1 Why it matters

CycleSync is likely to monetize through:

- usage gating;
- paid reminders;
- paid premium protocol execution features;
- specialist consultations;
- later packages or subscription modes.

### 14.2 Core commercial metrics

- first paid conversion rate;
- paid reminder activation rate;
- search-only free usage vs conversion;
- consultation booking conversion;
- conversion by entry point;
- feature usage before payment;
- retention of paid users vs free users.

### 14.3 Core events

Examples:

- `access_key_redeemed`
- `feature_paywall_seen`
- `paid_feature_unlocked`
- `consultation_checkout_started`
- `consultation_paid`
- `reminder_subscription_enabled`

---

## 15. Suggested event taxonomy

At the top level, analytics events should be grouped into families such as:

- `search_*`
- `draft_*`
- `protocol_*`
- `pulse_plan_*`
- `reminder_*`
- `adherence_*`
- `lab_*`
- `ai_*`
- `expert_*`
- `commercial_*`
- `catalog_*`

This creates a clean event namespace and avoids handler-level chaos.

---

## 16. Projection groups

The analytics layer should support derived views such as:

### 16.1 Product health views

- search quality summary;
- draft funnel summary;
- protocol activation summary;
- reminder response summary;
- adherence/broken-rate summary.

### 16.2 Monitoring views

- labs activity summary;
- AI triage summary;
- expert escalation summary.

### 16.3 Revenue/commercial views

- feature unlock summary;
- paid reminder usage;
- consultation conversion;
- revenue by feature later.

### 16.4 Catalog growth views

- top missing products;
- top missing aliases;
- not-found demand clusters.

---

## 17. Analytics storage strategy

### 17.1 Raw events

A raw `analytics_events` table or equivalent append-only event store should capture normalized event input.

### 17.2 Derived projections

Separate projection tables/materialized summaries should support fast dashboards and reporting.

### 17.3 Rebuildability rule

Whenever practical, key projections should be rebuildable from raw events.

### 17.4 Important rule

Analytics must not become the source of transactional truth.

---

## 18. Operational dashboards the system should support later

Even without building full dashboards immediately, the analytics model should support later views like:

- daily product health summary;
- search failure dashboard;
- activation funnel dashboard;
- reminder/adherence discipline dashboard;
- lab monitoring engagement dashboard;
- expert workload / response dashboard;
- monetization summary dashboard.

---

## 19. Commercial questions analytics should answer

This is where your monetization question matters.

Analytics should help answer:

- do users search but never calculate?
- do they calculate but not confirm?
- do they confirm but refuse reminders?
- do reminders improve retention and adherence enough to justify paywalling?
- how many users reach labs stage?
- how many users convert to consultation?
- which feature is the strongest monetization trigger?

If you do not measure these, monetization becomes guessing.

---

## 20. Guardrails

The analytics subsystem must avoid the following mistakes.

### 20.1 Handler-log analytics

Do not rely on random bot logs as the primary analytics source.

### 20.2 Vanity-only metrics

Do not overfocus on superficial counts that do not explain behavior.

### 20.3 Commercial blindness

Do not delay monetization-relevant event tracking until “later”.

### 20.4 Derived-truth inversion

Do not let analytics projections replace transactional truth.

### 20.5 Search-first neglect

Do not under-instrument search in a search-first product.

### 20.6 Reminder/adherence under-instrumentation

Do not track only reminder sends while ignoring what the user actually did.

---

## 21. Recommended future dependent documents

This analytics document should feed the creation of:

- `docs/71_event_catalog.md`
- `docs/72_product_health_views.md`
- `docs/73_commercial_metrics.md`
- `docs/74_catalog_growth_metrics.md`
- `docs/75_specialist_operational_metrics.md`

These names are recommendations and may change.

---

## 22. Final analytics statement

CycleSync analytics must be built as a first-class derived layer from day one.

It must reflect the real product spine:

- search;
- draft;
- protocol;
- pulse plan;
- reminders;
- adherence;
- labs;
- AI triage;
- expert cases;
- monetization.

If analytics is built correctly, CycleSync will know:

- what users value;
- where they fall off;
- whether reminders truly matter;
- whether search is working;
- whether the specialist layer is commercially justified;
- and which paid features users actually want.

If built late or badly, the product will be blind while pretending to be smart.
