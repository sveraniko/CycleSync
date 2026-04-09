# CycleSync Data Model (PostgreSQL)

> Data model document for **CycleSync**.

---

## 1. Purpose of this document

This document translates the architecture and domain model of CycleSync into a PostgreSQL-oriented data model strategy.

Its goals are to:

- define schema-level separation and data ownership boundaries;
- map core domain entities into relational storage structures;
- distinguish transactional truth from projections/read models;
- establish key identifier conventions;
- define index and constraint strategy;
- prepare the foundation for migrations, repositories, event catalog and implementation.

This document is **not**:

- a full Alembic migration listing;
- a final column-by-column SQL dump;
- a DTO catalog;
- a performance benchmark plan;
- a search ranking document;
- a reminder/adherence state-machine document.

Those belong in separate docs.

---

## 2. Data model principles

### 2.1 Transactional truth first

The write model must preserve clear transactional truth for:

- compound catalog;
- user registry;
- protocols;
- pulse plans;
- reminders;
- adherence;
- labs;
- expert cases.

Projections, search docs, AI summaries and analytics views must remain derived layers.

### 2.2 Algorithm-centered storage

The data model must preserve the fact that CycleSync is centered on `pulse_engine`.

That means:

- protocol inputs are stored explicitly;
- pulse-plan outputs are stored explicitly;
- recalculated plans do not silently overwrite history;
- reminders derive from pulse-plan truth, not from ad hoc UI state.

### 2.3 Catalog and user truth must remain separated

The product has:

- a **compound catalog truth**;
- a **user/protocol truth**.

These must never collapse into one muddled table family.

### 2.4 Stable internal identifiers

All primary entities must use stable internal IDs.
External identifiers such as Telegram user IDs, sheet row IDs, filenames or search strings must remain secondary references.

### 2.5 Explicit lifecycle state

State-bearing entities must store explicit state/status columns, not rely on inference from random timestamps.

### 2.6 Derived views must be rebuildable

Search and analytics projections should be disposable and rebuildable from transactional truth and/or event history.

### 2.7 Auditability where it matters

Protocol changes, pulse-plan supersession, reminder actions, lab uploads and expert-case interactions must be traceable.

### 2.8 Safety through constrained writes

Normal user writes must not allow silent corruption of schedule truth.
Low-level manual editing belongs to specialist/admin flows, not to ordinary write paths.

---

## 3. PostgreSQL storage strategy

### 3.1 Initial storage decision

CycleSync should start with:

- **one PostgreSQL cluster / logical database**;
- **schema-level separation by bounded context**;
- **one migration chain**;
- explicit projection schemas;
- explicit outbox/event storage if event architecture is adopted.

### 3.2 Why one DB is correct at MVP stage

The following are tightly related and do not justify physical separation at day one:

- protocol creation;
- pulse-plan computation;
- reminder generation;
- adherence logging;
- labs history;
- AI assessments;
- expert-case assembly.

Multiple physical databases now would only add:

- operational burden;
- migration complexity;
- debugging pain;
- accidental inconsistency.

### 3.3 Recommended schema grouping

Illustrative schema grouping:

- `compound_catalog`
- `user_registry`
- `protocols`
- `pulse_engine`
- `reminders`
- `adherence`
- `labs`
- `ai_triage`
- `expert_cases`
- `search_read`
- `analytics_raw`
- `analytics_views`
- `ops`

Names may change later, but separation intent must remain.

---

## 4. Identifier and metadata conventions

### 4.1 Primary key strategy

Recommended:

- UUIDv7 or equivalent sortable UUIDs for primary entity IDs;
- explicit surrogate keys for all core aggregates;
- avoid natural PKs for user-entered or external values.

### 4.2 Common metadata fields

Most transactional tables should include where relevant:

- `id`
- `created_at`
- `updated_at`
- `status`
- `archived_at` (if soft archive is needed)
- `version` (where optimistic concurrency matters)

### 4.3 External identity references

External identity references should be stored explicitly, for example:

- `telegram_user_id`
- `google_sheet_row_key`
- `external_case_ref`

These must not replace internal IDs.

---

## 5. Schema-by-schema model

## 5.1 `compound_catalog`

### Purpose

Stores the canonical searchable catalog of preparations and their pharmacokinetic-relevant metadata.

### Core tables

#### `brands`

Purpose:

- normalize manufacturer / lab identity;
- support aliasing and search enrichment.

Candidate columns:

- `brand_id` PK
- `display_name`
- `normalized_name`
- `status`
- `country_code` (optional)
- `created_at`
- `updated_at`

Indexes:

- unique index on `normalized_name` where feasible
- index on `status`

#### `brand_aliases`

Purpose:

- search support for noisy spelling / transliteration / copy-paste forms.

Candidate columns:

- `brand_alias_id` PK
- `brand_id` FK -> `brands`
- `alias_text`
- `normalized_alias`
- `created_at`

Indexes:

- index on `brand_id`
- index on `normalized_alias`

#### `substances`

Purpose:

- canonical active ingredient registry.

Candidate columns:

- `substance_id` PK
- `display_name`
- `normalized_name`
- `status`
- `created_at`
- `updated_at`

Indexes:

- unique index on `normalized_name`

#### `substance_aliases`

Purpose:

- support search by alternate substance wording.

Candidate columns:

- `substance_alias_id` PK
- `substance_id` FK
- `alias_text`
- `normalized_alias`

#### `esters`

Purpose:

- canonical ester registry used by search and scheduling.

Candidate columns:

- `ester_id` PK
- `display_name`
- `normalized_name`
- `half_life_days`
- `status`
- `created_at`
- `updated_at`

Indexes:

- unique index on `normalized_name`
- index on `half_life_days`

#### `compounds`

Purpose:

- concrete searchable product entities.

Candidate columns:

- `compound_id` PK
- `brand_id` FK -> `brands`
- `display_name`
- `normalized_name`
- `trade_name`
- `release_form`
- `packaging_label`
- `primary_media_asset_id` (optional, reference only)
- `default_volume_limit_ml` (optional)
- `official_url` (optional)
- `authenticity_note` (optional)
- `status`
- `source`
- `created_at`
- `updated_at`

Indexes:

- index on `brand_id`
- index on `normalized_name`
- index on `trade_name`
- index on `status`

#### `compound_aliases`

Purpose:

- search support for alternate trade spellings, transliteration and tokenized names.

Candidate columns:

- `compound_alias_id` PK
- `compound_id` FK -> `compounds`
- `alias_text`
- `normalized_alias`
- `created_at`

Indexes:

- index on `compound_id`
- index on `normalized_alias`

#### `compound_composition_entries`

Purpose:

- represent product composition.

Candidate columns:

- `compound_composition_entry_id` PK
- `compound_id` FK -> `compounds`
- `substance_id` FK -> `substances`
- `ester_id` FK -> `esters` nullable
- `amount_mg`
- `amount_unit`
- `concentration_mg_per_ml` nullable
- `sequence_no`
- `notes`
- `created_at`

Indexes:

- index on `compound_id`
- index on `substance_id`
- index on `ester_id`
- composite index on (`substance_id`, `amount_mg`)
- composite index on (`ester_id`, `amount_mg`)

#### `compound_media_links`

Purpose:

- store references to images/video/documents linked to the product.

Candidate columns:

- `compound_media_link_id` PK
- `compound_id` FK
- `media_asset_id`
- `media_role`
- `sort_order`
- `created_at`

#### `catalog_sync_runs`

Purpose:

- trace sync from Google Sheets.

Candidate columns:

- `catalog_sync_run_id` PK
- `source_name`
- `status`
- `started_at`
- `finished_at`
- `stats_json`
- `error_text` nullable

---

## 5.2 `user_registry`

### Purpose

Stores canonical user identity and base preferences.

### Core tables

#### `users`

Candidate columns:

- `user_id` PK
- `telegram_user_id` unique
- `display_name`
- `username` nullable
- `status`
- `timezone`
- `language_code` nullable
- `created_at`
- `updated_at`
- `last_activity_at`

Indexes:

- unique index on `telegram_user_id`
- index on `status`
- index on `last_activity_at`

#### `user_profiles`

Candidate columns:

- `user_profile_id` PK
- `user_id` unique FK -> `users`
- `sex` nullable
- `birth_date` nullable
- `height_cm` nullable
- `weight_kg` nullable
- `goal` nullable
- `notes` nullable
- `created_at`
- `updated_at`

Indexes:

- unique index on `user_id`

#### `user_preferences`

Candidate columns:

- `user_preference_id` PK
- `user_id` unique FK
- `reminders_enabled`
- `preferred_reminder_hour` nullable
- `voice_search_enabled`
- `created_at`
- `updated_at`

#### `user_limit_profiles`

Candidate columns:

- `user_limit_profile_id` PK
- `user_id` unique FK
- `max_injection_volume_ml` nullable
- `max_injections_per_week` nullable
- `notes` nullable
- `created_at`
- `updated_at`

---

## 5.3 `protocols`

### Purpose

Stores user-selected protocol truth and its lifecycle.

### Core tables

#### `protocols`

Candidate columns:

- `protocol_id` PK
- `user_id` FK -> `user_registry.users`
- `status`
- `preset_code`
- `weekly_target_mg`
- `duration_weeks`
- `start_date`
- `max_injection_volume_ml` nullable
- `max_injections_per_week` nullable
- `specialist_locked` default false
- `created_at`
- `updated_at`
- `confirmed_at` nullable

Indexes:

- index on `user_id`
- index on `status`
- index on `preset_code`
- index on `start_date`

#### `protocol_compounds`

Candidate columns:

- `protocol_line_id` PK
- `protocol_id` FK -> `protocols`
- `compound_id` FK -> `compound_catalog.compounds`
- `position`
- `is_required`
- `notes` nullable
- `created_at`

Indexes:

- index on `protocol_id`
- index on `compound_id`
- unique index on (`protocol_id`, `position`)

#### `protocol_constraints`

Purpose:

- explicit override storage beyond columns in `protocols` if needed.

Candidate columns:

- `protocol_constraint_id` PK
- `protocol_id` FK
- `constraint_code`
- `constraint_value_json`
- `created_at`

Indexes:

- index on `protocol_id`
- unique index on (`protocol_id`, `constraint_code`)

#### `protocol_state_log`

Purpose:

- trace lifecycle changes.

Candidate columns:

- `protocol_state_log_id` PK
- `protocol_id` FK
- `from_status`
- `to_status`
- `changed_at`
- `changed_by_role`
- `changed_by_user_id` nullable
- `note` nullable

Indexes:

- index on `protocol_id`
- index on `changed_at`

---

## 5.4 `pulse_engine`

### Purpose

Stores computed schedule truth.

### Core tables

#### `pulse_plans`

Candidate columns:

- `pulse_plan_id` PK
- `protocol_id` FK -> `protocols.protocols`
- `algorithm_version`
- `preset_code`
- `window_days`
- `flatness_score` nullable
- `estimated_injection_frequency` nullable
- `status`
- `created_at`
- `superseded_by_pulse_plan_id` nullable self-FK

Indexes:

- index on `protocol_id`
- index on `preset_code`
- index on `status`
- index on `created_at`

#### `pulse_plan_lines`

Candidate columns:

- `pulse_plan_line_id` PK
- `pulse_plan_id` FK -> `pulse_plans`
- `protocol_line_id` FK -> `protocols.protocol_compounds`
- `day_offset`
- `sequence_order`
- `dose_mg`
- `volume_ml`
- `created_at`

Indexes:

- index on `pulse_plan_id`
- composite index on (`pulse_plan_id`, `day_offset`, `sequence_order`)
- index on `protocol_line_id`

#### `pulse_plan_summary`

Optional summary table if read optimization is needed.

Candidate columns:

- `pulse_plan_summary_id` PK
- `pulse_plan_id` unique FK
- `total_injections`
- `avg_volume_ml`
- `peak_volume_ml` nullable
- `computed_at`

### Important rule

`pulse_plans` and `pulse_plan_lines` must preserve plan history.
A new computation should create a new plan, not mutate old line truth silently.

---

## 5.5 `reminders`

### Purpose

Stores scheduling and dispatch state of reminders.

### Core tables

#### `reminder_events`

Candidate columns:

- `reminder_event_id` PK
- `user_id` FK -> `user_registry.users`
- `protocol_id` FK -> `protocols.protocols`
- `pulse_plan_line_id` FK -> `pulse_engine.pulse_plan_lines` nullable
- `reminder_type`
- `scheduled_for_utc`
- `status`
- `created_at`
- `updated_at`

Indexes:

- index on `user_id`
- index on `protocol_id`
- index on `pulse_plan_line_id`
- composite index on (`status`, `scheduled_for_utc`)

#### `reminder_dispatches`

Candidate columns:

- `dispatch_id` PK
- `reminder_event_id` FK -> `reminder_events`
- `attempt_count`
- `delivery_status`
- `telegram_message_ref` nullable
- `sent_at`
- `error_text` nullable

Indexes:

- index on `reminder_event_id`
- index on `sent_at`

#### `reminder_rules`

Optional policy table.

Candidate columns:

- `reminder_rule_id` PK
- `rule_code`
- `description`
- `is_active`

---

## 5.6 `adherence`

### Purpose

Stores actual user compliance truth.

### Core tables

#### `adherence_actions`

Candidate columns:

- `reminder_action_id` PK
- `reminder_event_id` FK -> `reminders.reminder_events`
- `user_id` FK -> `user_registry.users`
- `action_type`
- `acted_at`
- `note` nullable
- `created_at`

Indexes:

- index on `reminder_event_id`
- index on `user_id`
- index on `action_type`
- index on `acted_at`

#### `adherence_snapshots`

Purpose:

- optional denormalized snapshots for fast user/protocol summaries.

Candidate columns:

- `adherence_snapshot_id` PK
- `user_id`
- `protocol_id`
- `computed_at`
- `done_count`
- `skip_count`
- `snooze_count`
- `adherence_score` nullable

Indexes:

- composite index on (`user_id`, `protocol_id`, `computed_at`)

### Important rule

Reminder dispatch state and adherence action state must remain separate tables.
Do not encode true compliance purely in `reminder_events.status`.

---

## 5.7 `labs`

### Purpose

Stores lab reports, attachments and structured markers.

### Core tables

#### `lab_reports`

Candidate columns:

- `lab_report_id` PK
- `user_id` FK -> `user_registry.users`
- `protocol_id` FK -> `protocols.protocols` nullable
- `report_date`
- `source_type`
- `status`
- `created_at`
- `updated_at`

Indexes:

- index on `user_id`
- index on `protocol_id`
- index on `report_date`
- index on `status`

#### `lab_attachments`

Candidate columns:

- `lab_attachment_id` PK
- `lab_report_id` FK -> `lab_reports`
- `storage_key`
- `mime_type`
- `file_name`
- `uploaded_at`

Indexes:

- index on `lab_report_id`

#### `lab_marker_values`

Candidate columns:

- `lab_marker_id` PK
- `lab_report_id` FK -> `lab_reports`
- `marker_code`
- `display_name`
- `value_numeric` nullable
- `value_text` nullable
- `unit`
- `reference_min` nullable
- `reference_max` nullable
- `reference_text` nullable
- `created_at`

Indexes:

- index on `lab_report_id`
- index on `marker_code`
- composite index on (`lab_report_id`, `marker_code`)

### Important rule

Lab truth must preserve original marker context and not be flattened beyond recognition.

---

## 5.8 `ai_triage`

### Purpose

Stores AI-generated preliminary assessments and flags.

### Core tables

#### `ai_assessments`

Candidate columns:

- `ai_assessment_id` PK
- `user_id` FK -> `user_registry.users`
- `lab_report_id` FK -> `labs.lab_reports`
- `protocol_id` FK -> `protocols.protocols` nullable
- `model_version`
- `status`
- `summary_text`
- `created_at`

Indexes:

- index on `user_id`
- index on `lab_report_id`
- index on `protocol_id`
- index on `created_at`

#### `ai_risk_flags`

Candidate columns:

- `risk_flag_id` PK
- `ai_assessment_id` FK -> `ai_assessments`
- `flag_code`
- `severity`
- `explanation`
- `created_at`

Indexes:

- index on `ai_assessment_id`
- index on `severity`

#### `ai_trend_observations`

Candidate columns:

- `trend_observation_id` PK
- `ai_assessment_id` FK
- `marker_code`
- `observation_text`
- `direction`
- `created_at`

Indexes:

- index on `ai_assessment_id`
- index on `marker_code`

### Important rule

AI assessments must remain versioned and attributable to concrete source data.
They must not overwrite lab truth.

---

## 5.9 `expert_cases`

### Purpose

Stores specialist case workflow and communication.

### Core tables

#### `expert_cases`

Candidate columns:

- `expert_case_id` PK
- `user_id` FK -> `user_registry.users`
- `status`
- `source`
- `opened_at`
- `closed_at` nullable
- `current_summary_snapshot` nullable
- `created_at`
- `updated_at`

Indexes:

- index on `user_id`
- index on `status`
- index on `opened_at`

#### `expert_case_links`

Purpose:

- link contextual entities to a case.

Candidate columns:

- `expert_case_link_id` PK
- `expert_case_id` FK -> `expert_cases`
- `entity_type`
- `entity_id`
- `created_at`

Indexes:

- index on `expert_case_id`
- composite index on (`entity_type`, `entity_id`)

#### `expert_messages`

Candidate columns:

- `expert_message_id` PK
- `expert_case_id` FK -> `expert_cases`
- `author_role`
- `author_user_id` nullable
- `body`
- `created_at`

Indexes:

- index on `expert_case_id`
- index on `created_at`

#### `expert_recommendations`

Optional structured follow-up table.

Candidate columns:

- `expert_recommendation_id` PK
- `expert_case_id` FK
- `recommendation_text`
- `follow_up_at` nullable
- `created_at`

---

## 5.10 `search_read`

### Purpose

Stores rebuildable read-models optimized for retrieval.

### Core tables

#### `compound_search_documents`

Candidate columns:

- `search_document_id` PK
- `compound_id` unique FK -> `compound_catalog.compounds`
- `document_json`
- `indexed_at`

Indexes:

- unique index on `compound_id`
- index on `indexed_at`

#### `user_search_documents`

Specialist-side projection.

Candidate columns:

- `search_document_id` PK
- `user_id` unique FK -> `user_registry.users`
- `document_json`
- `indexed_at`

#### `search_query_logs`

Purpose:

- track successful / unsuccessful searches;
- feed catalog enrichment.

Candidate columns:

- `search_query_log_id` PK
- `user_id` nullable
- `query_text`
- `normalized_query`
- `query_source`
- `found_count`
- `top_hit_compound_id` nullable
- `created_at`

Indexes:

- index on `created_at`
- index on `normalized_query`
- index on `found_count`

### Important rule

These tables are not transactional truth. They may be rebuilt or reindexed.

---

## 5.11 `analytics_raw` and `analytics_views`

### Purpose

Stores raw events and derived metric projections.

### Core tables

#### `analytics_events`

Candidate columns:

- `analytics_event_id` PK
- `event_type`
- `entity_type`
- `entity_id`
- `occurred_at`
- `source_context`
- `payload_json`
- `created_at`

Indexes:

- index on `event_type`
- index on `occurred_at`
- composite index on (`entity_type`, `entity_id`)

#### `daily_metrics`

Illustrative summary projection.

Candidate columns:

- `metric_date`
- `metric_key`
- `metric_value`
- `segment_json` nullable
- `computed_at`

Indexes:

- composite index on (`metric_date`, `metric_key`)

### Rule

Analytics tables are derived and may lag behind write-model truth.

---

## 5.12 `ops`

### Purpose

Operational/technical metadata.

### Candidate tables

- `outbox_events`
- `job_runs`
- `job_failures`
- `projection_checkpoints`
- `feature_flags` (optional)
- `system_settings` (optional)

These are not product domain tables, but they are critical for reliable operations.

---

## 6. Cross-schema reference rules

Cross-schema relationships must be explicit and disciplined.

### 6.1 Allowed references

- `protocols.protocols.user_id` -> `user_registry.users.user_id`
- `protocols.protocol_compounds.compound_id` -> `compound_catalog.compounds.compound_id`
- `pulse_engine.pulse_plans.protocol_id` -> `protocols.protocols.protocol_id`
- `pulse_engine.pulse_plan_lines.protocol_line_id` -> `protocols.protocol_compounds.protocol_line_id`
- `reminders.reminder_events.user_id` -> `user_registry.users.user_id`
- `reminders.reminder_events.protocol_id` -> `protocols.protocols.protocol_id`
- `reminders.reminder_events.pulse_plan_line_id` -> `pulse_engine.pulse_plan_lines.pulse_plan_line_id`
- `adherence.adherence_actions.reminder_event_id` -> `reminders.reminder_events.reminder_event_id`
- `labs.lab_reports.user_id` -> `user_registry.users.user_id`
- `labs.lab_reports.protocol_id` -> `protocols.protocols.protocol_id`
- `ai_triage.ai_assessments.lab_report_id` -> `labs.lab_reports.lab_report_id`
- `expert_cases.expert_cases.user_id` -> `user_registry.users.user_id`

### 6.2 Discouraged references

- embedding full compound truth inside protocol rows;
- embedding user identity truth inside expert case rows;
- using JSON blobs instead of normalized relations where search/scheduling depends on structure;
- storing actual adherence truth only in Telegram message metadata.

---

## 7. State-bearing tables and transition tracking

The following tables should be treated as explicit state-bearing records:

- `protocols.protocols`
- `pulse_engine.pulse_plans`
- `reminders.reminder_events`
- `labs.lab_reports`
- `ai_triage.ai_assessments`
- `expert_cases.expert_cases`

For major lifecycle objects, state transitions should be traceable through:

- state log tables; or
- domain events + timestamps; or
- both, depending on operational need.

---

## 8. Write model vs read model distinction

### 8.1 Write model

Transactional truth belongs in:

- `compound_catalog.*`
- `user_registry.*`
- `protocols.*`
- `pulse_engine.*`
- `reminders.*`
- `adherence.*`
- `labs.*`
- `ai_triage.*`
- `expert_cases.*`

### 8.2 Read / projection model

Derived representations belong in:

- `search_read.*`
- `analytics_views.*`
- optional specialist summary projections later

### 8.3 Rule

Do not query heavy operational summaries directly from normalized write tables on every Telegram request if a projection can serve the flow better.

---

## 9. Indexing strategy

### 9.1 General indexing rules

Every FK should have an index.
Every status-bearing table should index `status` where status-based filtering is common.
Time-driven workers should have indexes on their schedule/retry timestamps.

### 9.2 Reminder worker indexes

Required:

- (`status`, `scheduled_for_utc`) on `reminder_events`

This is essential for efficient polling.

### 9.3 Search-related indexes

Search documents live in projections, but the transactional catalog still needs supporting indexes on:

- normalized product names;
- brand references;
- substance/ester composition entries.

### 9.4 Analytics indexes

Event tables need:

- time-based index;
- event-type index;
- entity-ref composite index.

---

## 10. Constraint strategy

### 10.1 Relational constraints

Use FK constraints for all cross-table ownership where practical.

Use unique constraints for:

- `users.telegram_user_id`
- `brands.normalized_name` (where enforced)
- `substances.normalized_name`
- `esters.normalized_name`
- one-to-one preference/profile tables via unique `user_id`
- one active search doc per source entity where appropriate

### 10.2 Check constraints

Recommended examples:

- non-negative `weekly_target_mg`
- positive `duration_weeks`
- non-negative `amount_mg`
- non-negative `volume_ml`
- valid enum-like states where represented as text

### 10.3 Domain vs database constraints

Do not try to encode all product rules in SQL checks.

Examples such as:

- preset compatibility;
- specialist lock behavior;
- pulse-plan supersession rules;
- adherence semantics

belong primarily in domain/application logic.

---

## 11. History, supersession and immutability rules

### 11.1 Protocol history

Protocol writes may be mutable while draft, but important state transitions must be traceable.

### 11.2 Pulse-plan history

Pulse plans should be treated as append-and-supersede artifacts.
A recomputation creates a new plan and links to the previous one.

### 11.3 Reminder history

Reminder dispatch attempts must not be lost.

### 11.4 Adherence history

Adherence actions must remain append-only or strictly traceable.

### 11.5 Lab history

Original reports and structured markers must remain historically queryable.

### 11.6 AI history

Re-running AI triage should create a new assessment version, not overwrite past assessment truth.

---

## 12. Projection rebuild strategy

The following should be considered rebuildable:

- compound search docs;
- user search docs;
- analytics views;
- adherence summary snapshots;
- specialist summary views later.

Projection rebuild should be driven by:

- source tables;
- outbox / event history where implemented;
- batch recompute tools.

---

## 13. Media / storage references

This doc does not define a dedicated `media` schema yet, but references to files should follow a consistent strategy.

Recommended pattern:

- store files in object storage;
- store `storage_key`, `mime_type`, `file_name`, `uploaded_at` in relational tables;
- do not embed blobs in core operational tables.

This is especially relevant for:

- lab attachments;
- compound media links;
- future generated documents.

---

## 14. Event-outbox compatibility

If CycleSync uses an outbox/event architecture, the data model should support it from the beginning.

Recommended `ops.outbox_events` candidate columns:

- `outbox_event_id` PK
- `event_type`
- `aggregate_type`
- `aggregate_id`
- `payload_json`
- `status`
- `created_at`
- `published_at` nullable
- `retry_count`

Indexes:

- composite index on (`status`, `created_at`)
- index on `aggregate_type`
- index on `aggregate_id`

---

## 15. Suggested migration order (conceptual)

Conceptually, the data model should be introduced in a stable order:

1. user registry
2. compound catalog
3. protocols
4. pulse engine
5. reminders
6. adherence
7. labs
8. ai_triage
9. expert_cases
10. search projections
11. analytics / ops

Exact Alembic files may differ, but dependency direction should remain stable.

---

## 16. What this data model must protect architecturally

Even in the first implementation, the data model must already protect:

- separation of catalog truth and user truth;
- separation of protocol truth and computed pulse-plan truth;
- separation of reminder dispatch state and adherence truth;
- traceable plan supersession;
- preserved lab history;
- preserved AI assessment history;
- clean specialist-case context assembly;
- rebuildable search and analytics layers.

If these are not protected early, the schema will quickly collapse into “just add another JSON field” chaos.

---

## 17. Recommended next dependent documents

This data model should feed the creation of:

- `docs/35_event_catalog.md`
- `docs/40_search_model.md`
- `docs/45_protocol_lifecycle.md`
- `docs/50_pulse_engine.md`
- `docs/55_reminders_and_adherence.md`
- `docs/60_labs_ai_and_expert_cases.md`
- `docs/70_analytics.md`
- `docs/80_integrations_and_infra.md`

---

## 18. Final data model statement

CycleSync’s PostgreSQL data model must preserve a clear distinction between:

- **compound catalog truth**;
- **user truth**;
- **protocol truth**;
- **computed pulse-plan truth**;
- **reminder dispatch truth**;
- **adherence truth**;
- **lab truth**;
- **AI-derived assessments**;
- **expert-case truth**;
- **rebuildable search/analytics projections**.

The schema must be stable enough for growth, but disciplined enough to avoid blending algorithmic core, user operations and derived layers into one unmaintainable swamp.

This document defines the relational spine of the system.
