# CycleSync Product Health Views

> Product health views and system-level status projections document for **CycleSync**.

---

## 1. Purpose of this document

This document defines the main product-health views of CycleSync.

Its goals are to:

- define what “system health” means at product level;
- define the high-value aggregated views the system, operator or owner should eventually see;
- connect events, analytics and projections into understandable operational summaries;
- describe how product quality is assessed across search, protocols, reminders, adherence, labs, AI and commercial layers;
- prevent analytics from becoming a pile of disconnected counters.

This document is **not**:

- a dashboard UI mockup;
- a BI tool configuration;
- a low-level SQL materialization spec;
- a telemetry infrastructure doc.

Those belong elsewhere.

---

## 2. Why product-health views matter

CycleSync is not a single-purpose bot.
It has multiple interdependent layers:

- search;
- draft and protocol creation;
- pulse-engine calculation;
- reminders;
- adherence;
- labs;
- AI triage;
- expert escalation;
- commercial feature gating.

Looking only at raw events is not enough.
The system needs higher-level views that answer:

- is the product actually working;
- are users getting to value;
- where is the system degrading;
- what is healthy vs broken;
- which layer is the bottleneck;
- whether monetized value is actually being used.

---

## 3. What “product health” means in CycleSync

Product health in CycleSync is not just uptime.

A healthy system is one where:

- search finds what users expect;
- drafts convert into protocols;
- pulse plans are successfully computed;
- reminders are delivered and acted upon;
- adherence remains strong enough to keep protocols alive;
- broken protocol rate is controlled;
- labs are being entered when relevant;
- AI triage is used meaningfully;
- expert escalation happens when needed, not because the rest of the system failed;
- paid value layers convert and retain users.

This is product health, not merely infrastructure health.

---

## 4. Product health view groups

CycleSync should organize product-health projections into the following groups:

1. Search Health
2. Activation Funnel Health
3. Pulse Engine Health
4. Reminder Delivery Health
5. Adherence / Protocol Integrity Health
6. Monitoring Health (labs + AI)
7. Specialist Escalation Health
8. Commercial Health
9. Catalog Growth Health
10. Global Product Health Summary

---

## 5. Search Health View

### 5.1 Purpose

Measure whether the front door of the product works.

### 5.2 Questions this view should answer

- are users finding compounds;
- are not-found rates acceptable;
- are voice searches working;
- are result lists producing `Open` / `+Draft` actions;
- are search failures blocking activation.

### 5.3 Core fields / metrics

Illustrative fields:

- total_searches
- zero_result_rate
- exact_hit_rate
- open_rate_from_results
- add_to_draft_rate_from_results
- voice_search_share
- top_not_found_queries
- brand_alias_failure_rate
- composition_query_success_rate

### 5.4 Health interpretation

Healthy search means:

- low enough zero-result rate;
- strong `+Draft` conversion;
- low repeated not-found clusters;
- acceptable voice success.

---

## 6. Activation Funnel Health View

### 6.1 Purpose

Measure whether users move from discovery to actual protocol creation.

### 6.2 Funnel stages

- search performed
- first compound added to draft
- draft expanded
- weekly target set
- duration set
- preset selected
- calculation requested
- pulse plan generated
- protocol confirmed
- protocol activated

### 6.3 Core fields / metrics

Illustrative fields:

- search_to_draft_rate
- draft_to_calculation_rate
- calculation_success_rate
- calculation_to_confirmation_rate
- confirmation_to_activation_rate
- average_time_to_first_confirmed_protocol
- dropoff_stage_top

### 6.4 Health interpretation

Healthy funnel means:

- users reach calculation;
- plans are feasible;
- confirmations happen;
- activations are not collapsing before execution starts.

---

## 7. Pulse Engine Health View

### 7.1 Purpose

Measure whether the system’s core engine is producing useful, feasible plans.

### 7.2 Questions it should answer

- how often plans are successfully computed;
- which presets are used most;
- where calculations fail;
- how often plans are recomputed;
- how often constraints make plans infeasible.

### 7.3 Core fields / metrics

Illustrative fields:

- pulse_plan_compute_count
- pulse_plan_success_rate
- pulse_plan_failure_rate
- top_failure_reasons
- preset_usage_distribution
- warning_rate_by_preset
- recomputation_rate
- average_plan_complexity

### 7.4 Health interpretation

A healthy pulse-engine layer means:

- high compute success for valid inputs;
- manageable failure reasons;
- presets actually behaving as distinct useful strategies;
- no explosion of infeasible plans under common flows.

---

## 8. Reminder Delivery Health View

### 8.1 Purpose

Measure whether the system can actually operationalize the pulse plan.

### 8.2 Questions it should answer

- are reminders being created;
- are they being delivered;
- are retries under control;
- are stale cards cleaned;
- is reminder infrastructure producing real action.

### 8.3 Core fields / metrics

Illustrative fields:

- reminders_scheduled
- reminders_sent
- delivery_success_rate
- retry_rate
- expired_rate
- cleaned_from_chat_rate
- reminders_disabled_rate
- response_rate_after_first_send

### 8.4 Health interpretation

Healthy reminder delivery means:

- strong delivery;
- controlled retries;
- low dead-card accumulation;
- active, timely interaction.

---

## 9. Adherence / Protocol Integrity Health View

This is one of the most important health projections in the whole product.

### 9.1 Purpose

Measure whether users are actually following the pulse plan and whether protocols remain trustworthy.

### 9.2 Questions it should answer

- how many actions are done vs skipped vs missed;
- how many protocols are degrading;
- how many become broken;
- which presets correlate with better or worse execution;
- how much value paid reminders are actually generating.

### 9.3 Core fields / metrics

Illustrative fields:

- done_rate
- snooze_rate
- skip_rate
- missed_rate
- adherence_score_distribution
- broken_protocol_rate
- time_to_broken_protocol
- active_protocol_integrity_ratio
- adherence_by_preset
- adherence_free_vs_paid

### 9.4 Health interpretation

Healthy execution means:

- good done rate;
- controlled missed/skip rates;
- acceptable broken-protocol rate;
- evidence that reminders and adherence logic preserve execution quality.

### 9.5 Why this view is special

Because CycleSync’s promise collapses if protocols are mathematically elegant but behaviorally broken.

---

## 10. Monitoring Health View (Labs + AI)

### 10.1 Purpose

Measure whether users move from execution into meaningful monitoring.

### 10.2 Questions it should answer

- are users entering lab data;
- do reports contain enough markers;
- how often AI triage is generated;
- whether AI is being used or ignored.

### 10.3 Core fields / metrics

Illustrative fields:

- lab_reports_created
- avg_markers_per_report
- panel_usage_distribution
- repeat_lab_submission_rate
- ai_assessment_count
- ai_assessment_open_rate
- ai_escalation_suggestion_rate
- time_from_lab_to_ai

### 10.4 Health interpretation

Healthy monitoring means:

- labs are not a dead module;
- structured reports are actually entering the system;
- AI adds usable follow-through rather than decorative noise.

---

## 11. Specialist Escalation Health View

### 11.1 Purpose

Measure whether the human expert layer is functioning properly.

### 11.2 Questions it should answer

- how many users escalate;
- how quickly cases are answered;
- whether escalations happen at meaningful moments;
- whether specialists are overloaded later.

### 11.3 Core fields / metrics

Illustrative fields:

- expert_cases_opened
- escalation_rate_from_ai
- escalation_rate_from_active_protocols
- median_time_to_first_reply
- median_case_duration
- open_case_backlog
- closed_case_rate

### 11.4 Health interpretation

Healthy specialist layer means:

- cases are answered in a useful time frame;
- backlog does not silently accumulate;
- the system is not escalating every confused user because earlier product layers failed.

---

## 12. Commercial Health View

### 12.1 Purpose

Measure whether the business model is aligned with real product value.

### 12.2 Questions it should answer

- do free users discover enough value to convert;
- do reminders convert as a paid layer;
- do consultations convert as premium labor;
- which paywall moments work;
- are paid users actually using the unlocked value.

### 12.3 Core fields / metrics

Illustrative fields:

- free_to_paid_execution_rate
- first_pay_conversion_rate
- reminder_unlock_rate
- paid_reminder_retention
- consultation_checkout_start_rate
- consultation_paid_rate
- paid_user_active_protocol_rate
- free_vs_paid_adherence_delta

### 12.4 Health interpretation

Healthy commercial layer means:

- the paywall follows value;
- paid users use what they paid for;
- monetization does not destroy activation.

---

## 13. Catalog Growth Health View

### 13.1 Purpose

Measure whether the internal compound registry is growing in response to real search demand.

### 13.2 Questions it should answer

- what users repeatedly search for but cannot find;
- whether alias coverage is improving;
- whether catalog updates reduce search failure.

### 13.3 Core fields / metrics

Illustrative fields:

- repeated_not_found_query_clusters
- top_missing_brands
- top_missing_compounds
- top_missing_composition_patterns
- alias_enrichment_effect
- post_sync_zero_result_delta

### 13.4 Health interpretation

Healthy catalog growth means:

- the team learns from not-found demand;
- search improves over time;
- alias coverage expands intentionally.

---

## 14. Global Product Health Summary

This is the top-level condensed projection.

### 14.1 Purpose

Provide one compact system-level health summary.

### 14.2 Suggested sections

- Search Health
- Activation Health
- Pulse Engine Health
- Reminder Health
- Protocol Integrity Health
- Monitoring Health
- Specialist Health
- Commercial Health
- Catalog Growth Health

### 14.3 Suggested qualitative status levels

Each section may be shown as:

- healthy
- watch
- degraded
- critical

### 14.4 Why this matters

Because operators and owners need a concise view, not a swamp of raw counters.

---

## 15. Product health vs infrastructure health

These views describe **product health**, not system uptime.

Examples of product degradation even when infrastructure is technically fine:

- search works but returns weak results;
- reminders send but adherence collapses;
- AI runs but nobody opens the summaries;
- specialist cases open but nobody answers in time;
- monetization exists but paid users do not retain.

So product-health views must remain distinct from DevOps monitoring.

---

## 16. View construction principles

### 16.1 Projection-driven

Product-health views should be built from event streams and summary projections, not from expensive ad hoc queries over all transactional tables on every request.

### 16.2 Time-window aware

Health should be assessed over explicit windows such as:

- today;
- rolling 7 days;
- rolling 30 days;
- protocol-lifetime context where relevant.

### 16.3 Trend-aware

A view should show not only the latest value but also direction where useful.

Examples:

- improving;
- stable;
- worsening.

### 16.4 Drill-down capable

Health views should remain summary-first but support drill-down later.

Example:

- `Reminder Health = degraded`
- drill down -> retries up, delivery stable, response down, skip rate up.

---

## 17. Relationship to events and analytics

These views are fed by:

- event catalog (`71_event_catalog.md`);
- analytics projections (`70_analytics.md`);
- domain-truth layers;
- reminder/adherence logic;
- commercial entitlements later.

A product-health view is therefore not a new truth source.
It is a synthesized interpretation layer.

---

## 18. Suggested owner/operator audience split

### 18.1 Operator-focused health views

Operators may care more about:

- reminder delivery;
- broken protocols;
- labs entry volume;
- expert backlog;
- search not-found clusters.

### 18.2 Owner-focused health views

Owners may care more about:

- activation;
- retention;
- paid conversion;
- paid reminder usage;
- consultation revenue/proxy metrics;
- catalog demand growth.

### 18.3 Why split matters

The same data should not be forced into one overloaded view for everybody.

---

## 19. Guardrails

The product-health layer must avoid the following mistakes.

### 19.1 Counter swamp

Do not produce endless metrics with no hierarchy or meaning.

### 19.2 Vanity health

Do not call a system healthy because traffic is high while protocol integrity is collapsing.

### 19.3 Projection-as-truth

Do not let health views replace the underlying domain truth.

### 19.4 Search-first neglect

Do not underweight search in a search-first product.

### 19.5 Broken-protocol blindness

Do not hide broken execution behind pleasant aggregate averages.

### 19.6 Commercial-only health distortion

Do not let revenue signals override the fact that the product may be operationally unhealthy.

---

## 20. Recommended future dependent documents

This document should feed the creation of:

- `docs/73_commercial_metrics.md`
- `docs/74_projection_rebuild_rules.md`
- `docs/75_specialist_operational_metrics.md`
- `docs/76_health_alerting_rules.md`

These names are recommendations and may change.

---

## 21. Final statement

CycleSync product-health views must transform raw event and metric noise into a clear answer to one question:

> **Is the product actually working as a discipline and monitoring system, or is it only pretending to?**

A healthy CycleSync is not just one that calculates.  
It is one that searches well, activates users, preserves protocol execution, captures adherence truth, supports monitoring, escalates intelligently and monetizes without breaking trust.

This document defines the summary-health spine of the system.
