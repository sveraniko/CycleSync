# CycleSync MVP Plan

> Delivery and implementation plan for **CycleSync MVP**.

---

## 1. Purpose of this document

This document translates the current CycleSync wiki into an implementation plan.

Its goals are to:

- define the MVP objective clearly;
- fix the technical stack for initial implementation;
- sequence work into practical implementation waves;
- clarify dependencies between modules;
- distinguish MVP-critical work from later extensions;
- reduce the risk of building modules in the wrong order.

This document is **not**:

- a sprint board;
- a ticket list;
- a marketing launch plan;
- a final staffing plan.

Those can be built later from this plan.

---

## 2. MVP objective

The MVP of CycleSync must prove one thing above all:

> **The system can take selected compounds plus a weekly target, compute a usable pulse plan, execute it through reminders, track whether the user follows it, and later attach structured lab monitoring and specialist escalation on top.**

If MVP proves that loop, the product is real.
If it fails to prove that loop, everything else is decoration.

---

## 3. MVP success criteria

MVP is successful if it can do the following end-to-end:

1. User searches compound(s) and adds them to draft.
2. User sets weekly target, duration and preset.
3. System computes a pulse plan.
4. User confirms protocol.
5. System schedules reminders.
6. User responds with `Done / Snooze / Skip`.
7. System tracks adherence and can mark protocol degradation/broken state.
8. User can manually enter structured lab values.
9. AI triage can generate a preliminary summary.
10. User can open a specialist case from that context.
11. Paid layers can be feature-gated without breaking the core product.

---

## 4. What is in MVP

### 4.1 Core product

- Telegram-first user flow
- Search-first entry
- Compound registry
- Draft flow
- Protocol creation
- Pulse engine with preset strategies
- Reminder system
- Adherence tracking
- Broken protocol logic

### 4.2 Monitoring layer

- Structured manual lab entry
- Marker library
- Internal lab panel support
- AI preliminary assessment
- Expert case opening and response flow

### 4.3 Commercial/access layer

- Free entry and limited exploration
- Feature gating for paid execution layer
- Specialist consultation as paid action
- Entitlement-based access model

### 4.4 System layers

- Analytics/events
- Search projections
- Projection rebuild rules
- Outbox-compatible event delivery policy

---

## 5. What is explicitly out of MVP

The following are not required for the first release:

- public storefront/catalog browsing;
- social/community layer;
- heavy OCR-first lab parsing;
- broad men’s health module;
- full training/nutrition coaching suite;
- broad external lab integrations;
- complex bundle marketplace;
- advanced semantic/vector search beyond practical need;
- mobile app outside Telegram.

These may come later, but they must not distort MVP execution.

---

## 6. Stack decision for MVP

## 6.1 Recommended baseline stack

CycleSync should stay very close to the TradeFlow stack.

Recommended MVP stack:

- **FastAPI**
- **Uvicorn**
- **Pydantic v2**
- **pydantic-settings**
- **SQLAlchemy 2.x asyncio**
- **asyncpg** for runtime PostgreSQL access
- **psycopg** for migration/admin tooling paths where needed
- **Alembic**
- **redis-py / redis.asyncio**
- **aiogram 3.x**
- **structlog**
- **httpx**
- **Meilisearch**
- **Google Sheets integration**

### 6.2 Why this stack is the correct baseline

FastAPI remains a modern production-ready API framework and its official release notes show active current releases, including 0.135.1 in March 2026. citeturn921781search8turn921781search0

aiogram remains a modern fully asynchronous Telegram framework, and the current docs show 3.27.0 with support updated to Bot API 9.4 in February 2026. citeturn921781search1turn921781search5

Pydantic is current in v2, and the docs currently show v2.12.5. citeturn921781search2

SQLAlchemy 2.0 remains the active ORM/documented release line, and the docs currently show 2.0.49 released on April 3, 2026. citeturn921781search23turn921781search7

Alembic remains the standard migration tool for SQLAlchemy and its official docs currently show version 1.18.4. citeturn504563search3turn504563search7

redis-py is the recommended Python Redis client and supports both synchronous and asynchronous APIs; Redis also documents that aioredis was merged into redis-py. citeturn504563search6turn504563search10turn504563search18

Meilisearch has an official Python client and official SDK support for Python. citeturn504563search1turn504563search0

### 6.3 Practical recommendation on Meilisearch integration

For CycleSync I recommend the same architectural stance as TradeFlow:

- **Meilisearch as engine**
- **thin internal adapter layer** around it
- no deep lock-in to SDK behavior across the whole codebase

That means:

- use the official client only behind an internal search gateway/adapter; or
- keep an even thinner HTTP wrapper if the team prefers maximal control.

The important thing is not the SDK religion. The important thing is that Meili is behind a clean interface.

### 6.4 OCR dependency decision

Because MVP uses structured manual lab entry first, OCR libraries should **not** be a required part of the MVP runtime path.

That means:

- no OCR-first dependency burden in MVP;
- OCR can remain future/optional.

### 6.5 Requests vs httpx

For application runtime, prefer `httpx` for async flows.

If `requests` remains only as a transitive/auxiliary dependency for auth or edge cases, that is acceptable, but it should not become the default app HTTP client.

### 6.6 OpenAI / LLM client

MVP will also need one explicit LLM integration package or thin API wrapper for AI triage.

Recommendation:

- keep this behind an internal `llm_gateway` abstraction;
- do not let model/provider logic leak across the codebase.

---

## 7. Architecture-to-delivery principle

Build in dependency order, not by excitement order.

That means:

- search before protocol flow;
- protocol flow before pulse-engine execution;
- pulse engine before reminders;
- reminders before adherence health logic;
- manual labs before AI triage;
- AI triage before specialist flow;
- entitlement/commercial hooks before monetized launch.

Do not start with shiny layers while the core chain is incomplete.

---

## 8. Delivery waves

## Wave 0 — Foundation and repo skeleton

### Goal

Create the technical base so the project can run cleanly.

### Includes

- repository skeleton
- app structure aligned with architecture
- FastAPI app shell
- aiogram bot shell
- config management
- structured logging
- PostgreSQL connectivity
- Redis connectivity
- Alembic baseline
- Docker / Compose setup
- health endpoints

### Done when

- local environment starts via Docker Compose
- DB migrations apply cleanly
- bot process and API process boot cleanly
- config/secrets pattern is stable

---

## Wave 1 — Compound catalog and search foundation

### Goal

Make search-first entry real.

### Includes

- compound catalog schema
- Google Sheets sync
- brand/substance/ester/composition data model
- Meilisearch integration through thin adapter
- search projection generation
- search endpoint / bot flow
- result list with `Open` and `+Draft`
- not-found query logging

### Done when

- compounds sync from sheet
- user can search by trade name/brand/substance
- results open compound card
- results can be added to draft
- Meili + fallback behavior works at basic level

---

## Wave 2 — Draft and protocol creation flow

### Goal

Allow the user to assemble a real candidate protocol.

### Includes

- draft context model
- add/remove/reorder draft compounds
- weekly target input
- duration input
- preset selection
- basic constraint input
- protocol draft persistence
- lifecycle states up to `calculated`

### Done when

- user can go from search to usable draft
- draft state persists correctly
- protocol calculation can be requested from the bot

---

## Wave 3 — Pulse Engine MVP

### Goal

Make the core differentiator real.

### Includes

- pulse-engine service boundary
- catalog input resolution
- preset handling
- calculation window logic
- volume/frequency constraint enforcement
- pulse-plan persistence
- pulse-plan preview rendering
- recalculation/supersession rules for draft stage

### Done when

- system computes feasible pulse plans from valid protocol inputs
- invalid inputs fail cleanly
- pulse-plan output is persisted and viewable
- presets behave distinctly enough to matter

---

## Wave 4 — Protocol confirmation, reminders and adherence

### Goal

Turn the pulse plan into real execution.

### Includes

- protocol confirmation/activation flow
- reminder event generation
- reminder worker
- `Done / Snooze / Skip` actions
- reminder state machine
- adherence action storage
- protocol health / broken-state logic
- reminder settings on/off
- stale card cleanup/edit/delete behavior

### Done when

- confirmed protocol activates reminders
- user actions are captured correctly
- protocol health can degrade and break
- reminder system behaves cleanly in chat

---

## Wave 5 — Marker library and structured lab entry

### Goal

Establish the monitoring layer with clean data.

### Includes

- marker library implementation
- internal panel definitions (minimum set)
- manual entry wizard
- lab report grouping by report date
- units + reference ranges storage
- lab history view

### Done when

- user can enter structured lab values
- system stores lab reports cleanly
- historical comparison groundwork exists

---

## Wave 6 — AI triage and expert case flow

### Goal

Turn monitoring data into actionable second-layer value.

### Includes

- llm gateway
- AI triage pipeline from structured lab data
- risk flags / summary output
- specialist case model
- specialist case creation flow
- specialist response thread
- specialist context assembly from protocol + adherence + labs + AI

### Done when

- user can generate AI summary from lab data
- user can open specialist case
- specialist receives structured context

---

## Wave 7 — Commercial and entitlement layer

### Goal

Make the product commercially operable without poisoning the core domains.

### Includes

- entitlement model implementation
- access key support
- feature gate checks
- free limit handling
- paid execution-layer unlocks
- specialist consultation payment gate
- commercial event emission

### Done when

- free users can explore
- paid users unlock reminders/execution layer
- consultation requires paid path
- access is entitlement-driven, not env-hacked

---

## Wave 8 — Analytics, projections and operational hardening

### Goal

Make the system measurable and stable enough for controlled production use.

### Includes

- analytics raw events
- key projections
- product health views
- projection rebuild tooling
- outbox delivery policy implementation
- lag/health visibility
- operational repair paths

### Done when

- system emits stable events
- analytics and health projections exist
- rebuild and replay logic exists for critical derived layers

---

## 9. Dependency order summary

Implementation dependency chain is:

1. foundation
2. catalog/search
3. draft/protocol input
4. pulse engine
5. reminders/adherence
6. labs/manual entry
7. AI + specialist cases
8. entitlements/commercial
9. analytics/projection hardening

This is the correct order because each later layer depends on real output from the previous one.

---

## 10. What can be parallelized safely

Some work can run in parallel without breaking sequencing.

### Parallel candidates

- marker library drafting while pulse engine implementation is happening
- entitlement model implementation skeleton while core execution layer stabilizes
- analytics event schema drafting while protocol/reminder flows are being built
- Meili adapter work in parallel with catalog schema implementation

### What should not be parallelized prematurely

- specialist flow before labs are structured
- commercial paywall logic before entitlement model exists
- health views before core event emissions are stable

---

## 11. Suggested MVP release slicing

### Release 0 — Internal alpha

- search
- draft
- pulse-engine MVP
- basic reminder flow
- no commercial launch yet or very controlled access key gating

### Release 1 — Controlled beta

- stable reminders/adherence
- basic broken protocol logic
- marker library + manual lab entry
- AI triage in limited scope
- access keys / free vs paid execution gate starts

### Release 2 — Paid early production

- specialist cases
- entitlement-driven paid execution layer
- paid consultation flow
- analytics and product health views

---

## 12. Technical stack summary for MVP

### Keep

- FastAPI
- Uvicorn
- Pydantic v2
- pydantic-settings
- SQLAlchemy 2 async
- asyncpg
- psycopg for migration/admin paths
- Alembic
- redis-py / redis.asyncio
- aiogram 3.x
- structlog
- httpx
- Meilisearch

### Add/define explicitly

- thin `search_gateway` abstraction over Meili
- thin `llm_gateway` abstraction for AI triage
- Google Sheets integration layer
- outbox event storage/dispatcher

### Do not make core MVP-dependent

- OCR-first stack
- heavy media parsing stack
- uncontrolled provider-specific SDK leakage everywhere

---

## 13. Key architectural non-negotiables during implementation

1. `pulse_engine` remains central
2. `compound_catalog` stays separate from `user_registry`
3. `protocol` truth != `pulse_plan` truth
4. `reminder` truth != `adherence` truth
5. labs stay structured/manual-first
6. entitlements stay separate from core domain state
7. projections remain rebuildable
8. outbox delivery stays reliable and idempotent

These are not style preferences. They are structural survival rules.

---

## 14. Risks and control points

### 14.1 Risk: Search underperforms

Mitigation:

- invest early in normalization and search projections;
- use not-found logging;
- test real-world query families.

### 14.2 Risk: Pulse-engine too ambitious too early

Mitigation:

- build MVP presets cleanly first;
- avoid overcomplicating the first working version;
- keep advanced strategy extensible.

### 14.3 Risk: Reminders become noisy/spammy

Mitigation:

- strict state machine;
- bounded retries;
- stale-card cleanup;
- adherence truth separated from send logic.

### 14.4 Risk: Labs module becomes OCR hell

Mitigation:

- stick to structured manual input first.

### 14.5 Risk: Commercial logic pollutes core flow

Mitigation:

- entitlement model first;
- feature-gate layer separate from protocol domain.

---

## 15. Definition of MVP readiness

CycleSync MVP is ready when:

- search-first entry works on real catalog data;
- user can move from search to draft to confirmed protocol;
- pulse plans compute reliably enough for MVP use;
- reminders execute and track adherence;
- broken protocol logic works;
- user can enter structured lab reports;
- AI triage can summarize labs;
- specialist case can be opened;
- paid execution layer can be gated cleanly;
- events, analytics and projections are not fake.

---

## 16. Recommended immediate next action after this plan

After fixing this plan, the next implementation move should be:

- create the repo/app skeleton aligned to the architecture;
- lock the stack in project config;
- then start Wave 0 and Wave 1.

Do not jump straight into pulse-engine code before the catalog/search/protocol scaffolding exists.

That is how otherwise smart people end up with a brilliant function living in a swamp.

---

## 17. Final statement

The correct MVP path for CycleSync is not:

- build random shiny modules;
- improvise access control;
- bolt analytics on later;
- and hope the core holds.

The correct path is:

- build the search-first input layer;
- build the protocol and pulse-engine core;
- build reminders and adherence;
- add structured monitoring;
- add specialist escalation;
- add commercial gating cleanly;
- harden with analytics and projections.

That sequence respects both the product truth and the technical dependencies.
