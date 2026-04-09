# CycleSync Pulse Engine

> Pulse-engine and scheduling core document for **CycleSync**.

---

## 1. Purpose of this document

This document defines the core mathematical and product logic of the CycleSync pulse engine.

Its goals are to:

- formalize what the engine is responsible for;
- define engine inputs and outputs;
- describe preset strategies;
- define scheduling windows and constraints;
- define flatness/stability goals;
- explain how a protocol becomes a pulse plan;
- separate user input freedom from engine-controlled math;
- prepare the foundation for implementation, state handling and testing.

This document is **not**:

- a medical recommendation document;
- a specialist manual;
- a UI wording spec;
- a detailed search doc;
- a reminder state-machine doc.

Those belong elsewhere.

---

## 2. Why Pulse Engine is the product core

CycleSync is not centered on catalog, search or AI.

Its central differentiator is this:

> **Given a known set of compounds, a weekly target, a duration and practical limits, the system computes a schedule that keeps the total pharmacological background as flat and stable as feasible.**

This matters because in real usage:

- users often combine compounds with different esters and concentrations;
- the same weekly amount can be distributed well or badly;
- poor distribution produces avoidable spikes and troughs;
- even specialists often calculate roughly, inconsistently or lazily;
- users cannot reliably do this math in their heads.

Therefore the pulse engine is not an implementation detail. It is the heart of the product.

---

## 3. Pulse Engine responsibility boundary

The pulse engine owns:

- interpretation of protocol input into a computable scheduling problem;
- strategy selection by preset;
- frequency/interval logic;
- window generation;
- dose/volume allocation across the window;
- flatness optimization;
- feasibility validation against constraints;
- pulse-plan generation.

The pulse engine does **not** own:

- compound catalog truth;
- user identity;
- reminder dispatch;
- adherence truth;
- lab history;
- AI triage;
- specialist judgment.

---

## 4. Core product principle of the engine

The engine exists to support the principle:

**Control and stability are more important than chaotic peaks.**

This means the engine optimizes for:

- stability over spectacle;
- repeatability over improvisation;
- schedule integrity over ad hoc injection convenience;
- mathematically explainable plan generation over forum-style guessing.

---

## 5. Input model

## 5.1 User-facing input model

A normal user is expected to provide:

- selected compounds from the internal catalog;
- weekly target (`weekly_target_mg` or equivalent overall target);
- duration in weeks;
- preset selection;
- max volume per injection;
- optional preferred max injections per week;
- optional start date.

### Important rule

A normal user should **not** manually micro-manage all low-level pharmacokinetic distribution parameters.

The engine, not the user, owns the difficult math.

## 5.2 Specialist-facing extension (later)

A later specialist mode may allow deeper override control such as:

- more explicit per-compound targeting;
- manual locking of compound proportions;
- stricter frequency control;
- advanced custom schedule steering.

But this is an extension, not the default user flow.

## 5.3 Catalog-derived inputs

For each selected compound the engine requires catalog data such as:

- composition entries;
- active substance(s);
- ester(s);
- half-life values;
- concentration values;
- release form;
- volume constraints where relevant.

Without valid half-life/concentration truth, automated calculation is not reliable.

---

## 6. Output model

The engine outputs a **Pulse Plan**.

A pulse plan contains:

- selected preset;
- calculation window;
- schedule lines by day offset;
- compound-specific dose allocation;
- volume allocation;
- estimated frequency summary;
- flatness/stability indicators;
- conflict/warning flags if present.

The pulse plan is then used to create:

- user calendar preview;
- protocol execution view;
- reminder chain;
- specialist context later.

---

## 7. Input normalization before calculation

Before actual calculation, the engine should normalize protocol inputs.

### 7.1 Compound resolution

Every selected draft line must resolve to a real `compound_id` and composition truth from catalog.

### 7.2 Weekly target resolution

The weekly target must be normalized into a form the engine can distribute across the selected compound set.

### 7.3 Duration normalization

Duration should be stored as weeks, but calculation may convert it into days and scheduling windows.

### 7.4 Constraint normalization

Volume and frequency limits should be normalized into numeric and strategy-compatible values.

### 7.5 Preset normalization

The engine must treat preset selection as an explicit strategy input, not as vague UI metadata.

---

## 8. Preset strategies

CycleSync should expose pulse-engine behavior through preset strategies, not through free-form user math.

## 8.1 Preset A — Unified Rhythm

### Product idea

A simplified schedule that aligns compounds into one shared working rhythm, with practical emphasis on usability and compact scheduling.

### When it is appropriate

- the user values simplicity;
- the user wants fewer distinct scheduling rhythms;
- the plan must remain easy to follow;
- volume constraints are still respected.

### Strategic logic

- choose a dominant rhythm anchor based on long-acting behavior;
- distribute relevant compounds into one unified cadence where feasible;
- preserve basic schedule coherence;
- avoid excessive complexity.

### Trade-off

This strategy is more convenient but may be less flat than more advanced options.

## 8.2 Preset B — Layered Pulse

### Product idea

Each compound follows its own optimal interval logic and the resulting layers are overlaid into one coherent calendar.

### When it is appropriate

- better flatness is desired;
- the user accepts more schedule complexity;
- compounds have materially different half-lives;
- volume limits require distribution across time.

### Strategic logic

- compute an ideal or near-ideal interval per compound;
- build compound-specific pulse layers;
- merge them into a calendar;
- minimize destructive stacking of peaks where feasible.

### Trade-off

This is a stronger stability strategy than Unified Rhythm, but harder for the user to follow.

## 8.3 Preset C — Golden Pulse / Conveyor

### Product idea

The flagship mode of CycleSync.

This strategy seeks the mathematically strongest “pharmacological weaving” of compounds across a calculation window so that the summed background is as close to a straight line as practical.

### When it is appropriate

- the protocol matters enough to justify heavier math;
- compounds differ significantly in half-life/composition behavior;
- the user wants the strongest stability-oriented schedule;
- the selected constraints still make such a schedule feasible.

### Strategic logic

- choose a calculation window;
- derive target intervals from half-life behavior;
- phase-shift schedule lines instead of blindly stacking them;
- optimize for flatness of the sum of layers;
- preserve practical feasibility.

### Trade-off

This is the strongest differentiator, but also the most complex preset.

---

## 9. Scheduling window model

The engine needs a calculation window.

## 9.1 Why a window exists

The engine cannot reason only in “one week” chunks because:

- compound half-lives differ;
- intervals may not align cleanly;
- stable layering emerges over time;
- some presets require phasing across a broader period.

## 9.2 Window role

The window is used to:

- place schedule lines;
- evaluate summed concentration behavior;
- compare candidate distributions;
- determine repeatable patterns.

## 9.3 Recommended MVP window strategy

MVP may use a bounded practical calculation window, such as:

- a derived common interval window;
- capped by a practical maximum (e.g. 42 days) if needed.

The exact formula belongs to implementation/testing detail, but the architectural rule is:

> **The engine must reason over a repeatable multi-day window, not over isolated single injections.**

---

## 10. Half-life and interval logic

### 10.1 Half-life as the primary driver

Half-life is the primary scheduling driver for engine rhythm selection.

### 10.2 Core heuristic

A key product heuristic is:

- intervals are often derived relative to half-life behavior;
- more stable layering typically requires injection rhythm significantly tighter than naive “once per half-life” thinking.

### 10.3 Product-safe phrasing

The engine should operate on catalog truth and internal formulas.
The user should receive schedule results, not raw pharmacokinetic algebra unless specialist/debug mode explicitly requires it later.

### 10.4 Missing or weak half-life data

If half-life data is missing or untrustworthy:

- that compound is not safely eligible for automated scheduling in normal mode;
- the system should fail explicitly or require specialist override.

---

## 11. Volume constraint model

Volume is not a cosmetic field. It is a hard practical scheduling constraint.

### 11.1 Why volume matters

Even if a theoretical schedule looks perfect, it may be unusable if per-event volume becomes impractical.

### 11.2 Volume cap behavior

The engine must respect:

- user max injection volume;
- compound-specific limits if catalog provides them;
- preset-specific distribution choices.

### 11.3 Engine responses to a volume conflict

If a candidate distribution exceeds per-event volume constraints, the engine may:

- redistribute schedule lines across more events;
- shift layering;
- reject the plan as infeasible under the chosen preset;
- suggest a different preset or looser user constraints.

### 11.4 Important rule

The engine must not silently output a physically impractical schedule.

---

## 12. Frequency constraint model

### 12.1 Frequency is secondary to stability, but still real

The product is not a comfort toy, but it must still respect human execution limits.

### 12.2 Frequency inputs

Possible inputs:

- user preferred max injections per week;
- specialist override later;
- preset-specific expectations.

### 12.3 Frequency conflict behavior

If a schedule cannot maintain acceptable flatness under a very strict frequency cap, the engine should:

- warn the user;
- suggest an alternative preset;
- surface the trade-off between comfort and stability.

### 12.4 Important product truth

The engine should not lie.
If stability requires higher frequency, the product must say so instead of fabricating a “conveniently smooth” fiction.

---

## 13. Flatness / stability objective

## 13.1 The real optimization target

The engine does not optimize for “how impressive the cycle sounds”.

It optimizes for:

- minimizing fluctuation of the summed background;
- reducing peak/trough spread;
- preserving schedule feasibility;
- respecting volume/frequency constraints.

## 13.2 Flatness as an internal objective

The engine should compute or approximate a flatness metric that compares candidate plans.

This metric may later be surfaced as:

- flatness score;
- stability score;
- warning delta vs simpler presets.

### 13.3 Why flatness matters product-wise

Flatness is not a nice-to-have statistic.
It is the engine’s expression of the product promise.

---

## 14. Calculation phases

The engine should conceptually run in phases.

### Phase 1 — Validate inputs

- resolve compounds;
- validate catalog completeness;
- validate target/duration;
- validate preset;
- validate constraints.

### Phase 2 — Build candidate schedule space

- derive interval logic;
- choose or derive window;
- create preset-specific schedule possibilities.

### Phase 3 — Evaluate candidates

- simulate layer distribution;
- estimate summed stability;
- detect volume/frequency violations;
- discard weak candidates.

### Phase 4 — Select pulse plan

- choose best feasible candidate under preset and constraints;
- generate schedule lines;
- generate summary metrics;
- attach warnings if trade-offs exist.

### Phase 5 — Persist plan

- store pulse plan;
- store lines;
- mark plan as current for protocol if confirmed;
- prepare handoff to reminders.

---

## 15. Calculation outcomes

The engine should produce one of the following classes of outcomes.

### 15.1 Successful feasible plan

The engine found a valid schedule respecting current preset and constraints.

### 15.2 Feasible with warnings

The engine found a plan, but one or more trade-offs are meaningful.

Examples:

- higher-than-preferred frequency;
- weaker flatness than target;
- schedule complexity is high.

### 15.3 Infeasible under current constraints

The engine cannot produce a plan that satisfies the chosen constraints.

Examples:

- volume cap too strict;
- frequency cap too strict;
- missing half-life truth;
- preset too restrictive for selected compounds.

### 15.4 Unsupported catalog/input case

The catalog truth is insufficient for safe automated scheduling.

---

## 16. Pulse plan semantics

A pulse plan is not just a calendar list.
It is a formally computed execution artifact.

### 16.1 Pulse plan must include

- the preset used;
- the algorithm version;
- the calculation window;
- one or more schedule lines;
- line ordering where multiple items share a day;
- summary metrics;
- warning flags if any.

### 16.2 Pulse plan must not be

- a mutable scratchpad;
- an inferred Telegram message;
- a free-text plan;
- a UI-only concept.

---

## 17. Recalculation and supersession

### 17.1 Why recalculation exists

Recalculation is necessary when protocol inputs materially change.

### 17.2 Recalculation rule

A recalculation must create a **new** pulse plan and explicitly supersede the old one.

### 17.3 History rule

Old pulse plans must remain queryable for:

- auditability;
- user history;
- specialist review;
- adherence context.

### 17.4 Active-plan caution

If a protocol is already active, recalculation becomes a serious lifecycle event and must not rewrite the past.

---

## 18. Engine relation to reminders

The pulse engine does not send reminders.

The pulse engine provides:

- pulse-plan lines;
- time structure;
- execution points.

The reminders subsystem transforms that into scheduled user-facing events.

### Important rule

Reminder generation must always derive from pulse-plan truth, not from duplicated UI logic.

---

## 19. Engine relation to adherence

The pulse engine does not know what the user actually did.

It defines what should happen.

Adherence later records what happened.

### Why this distinction matters

Because:

- a perfect plan may be poorly followed;
- lab interpretation later depends on both plan truth and adherence truth;
- specialist escalation needs both layers.

---

## 20. Engine relation to labs and specialist flow

Labs and expert cases sit downstream of protocol execution.

### 20.1 Labs

Labs provide observation of what happened during execution.

### 20.2 AI triage

AI interprets observations and trends, not scheduling math itself.

### 20.3 Specialist

The specialist works on top of:

- selected compounds;
- protocol truth;
- pulse-plan truth;
- adherence truth;
- lab history.

The specialist does not replace the engine’s role as the core planner.

---

## 21. Engine-specific guardrails

The pulse engine must avoid the following mistakes.

### 21.1 User-as-manual-algorithm illusion

Do not expose a level of low-level manual control that destroys the product’s main value.

### 21.2 Weekly target without distribution logic

Do not treat weekly target as sufficient by itself. The whole point is the distribution.

### 21.3 Flatness ignored in favor of convenience

Do not silently prioritize convenience while pretending the plan is “ideal”.

### 21.4 Volume-blind optimization

Do not output beautiful but impractical schedules.

### 21.5 Recalculation as overwrite

Do not overwrite previous pulse-plan truth when a new plan is computed.

### 21.6 Preset without distinct logic

Do not create three presets that are really the same engine behavior with different labels. Each preset must express a real strategy difference.

---

## 22. Recommended test categories for the engine

The eventual implementation should be testable along categories such as:

- exact compound resolution validity;
- missing half-life failure paths;
- volume-cap enforcement;
- frequency-cap trade-offs;
- preset differentiation behavior;
- reproducible pulse-plan generation;
- plan supersession behavior;
- reminder handoff integrity.

This is not the full test plan, only the minimal categories the design already implies.

---

## 23. Recommended future dependent documents

This pulse engine document should feed the creation of:

- `docs/51_preset_rules.md`
- `docs/52_flatness_and_scoring.md`
- `docs/53_engine_validation_and_failure_paths.md`
- `docs/55_reminders_and_adherence.md`
- `docs/60_labs_ai_and_expert_cases.md`

These names are recommendations and may be adjusted.

---

## 24. Final pulse-engine statement

CycleSync Pulse Engine is the **central mathematical system** of the product.

Its job is not simply to “split a weekly amount across days”, but to:

- interpret protocol intent;
- respect catalog truth;
- account for half-life-driven behavior;
- respect real-world constraints;
- choose a strategy through presets;
- generate the flattest feasible pulse plan;
- preserve history when recalculated;
- hand off a precise execution structure to the rest of the system.

If this engine is weak, the whole product becomes a dressed-up draft board with reminders.  
If this engine is strong, CycleSync becomes what it is supposed to be: a system that calculates better than most people in this space can think manually.
