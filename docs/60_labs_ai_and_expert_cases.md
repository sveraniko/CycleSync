# CycleSync Labs, AI Triage and Expert Cases

> Labs, AI-triage and specialist-escalation document for **CycleSync**.

---

## 1. Purpose of this document

This document defines the second-layer value system of CycleSync:

- structured lab data intake;
- historical monitoring;
- AI-based preliminary assessment;
- specialist escalation and case handling.

Its goals are to:

- define how lab information enters the product;
- define why structured manual input is the correct MVP path;
- define the role of marker libraries and lab panels;
- define AI triage responsibilities and limitations;
- define expert-case assembly and specialist flow;
- define how lab context connects to protocol truth and adherence history.

This document is **not**:

- a pulse-engine formula spec;
- a general medical guideline;
- a legal compliance manual;
- a specialist treatment manual.

Those belong elsewhere.

---

## 2. Position of this subsystem inside the product

CycleSync has two value layers.

### Layer 1 — Core value

- pulse-engine;
- protocol execution;
- reminders;
- adherence.

### Layer 2 — Monitoring and escalation

- lab tracking;
- AI triage;
- expert escalation.

This document describes **Layer 2**.

Important rule:

> Labs, AI and specialist workflows do not replace the product core. They operate on top of protocol, pulse-plan and adherence truth.

---

## 3. Core product principle of this layer

The product should not rely on fuzzy OCR-first pipelines for a domain where numerical accuracy matters.

Therefore the correct MVP principle is:

> **Structured manual entry first. OCR later, if ever justified.**

This is not a limitation. It is a product-quality decision.

Because for CycleSync:

- values matter more than file decoration;
- exact marker data matters more than uploaded PDFs;
- AI needs structured truth, not noisy media guesses;
- specialist needs clean comparable data, not screenshots and chaos.

---

## 4. Why manual structured entry is the right MVP choice

### 4.1 OCR is not free value

If users upload photos/PDFs and the system tries to parse them automatically, the product inherits:

- OCR errors;
- inconsistent layout parsing;
- language problems;
- reference range extraction errors;
- unit confusion;
- heavy media handling;
- higher support/debug burden.

### 4.2 Structured manual entry gives better product truth

A structured input wizard gives:

- explicit marker identity;
- explicit value;
- explicit unit;
- optional lab reference ranges;
- clean storage in relational form;
- clean comparison across time;
- better AI input;
- better specialist context.

### 4.3 Manual input is acceptable for serious users

The target user is not passively browsing memes.
They are asking for real monitoring and possibly specialist review.

If the user wants meaningful analysis, entering key marker values manually is an acceptable and even healthy friction.

---

## 5. MVP decision: no OCR-first intake

### 5.1 MVP intake mode

MVP should use:

- **structured manual entry wizard**;
- optional simple note field;
- optional later upload of raw file only for archive/reference, not for primary parsing.

### 5.2 Why this is the correct trade-off

This avoids:

- OCR complexity;
- parser hallucinations;
- false trust in extracted data;
- media-heavy infrastructure burden.

### 5.3 Possible future expansion

Later, the system may support:

- optional attachment upload;
- OCR as assistive extraction;
- user confirmation of parsed values;
- template-based import for specific lab formats.

But none of that should be required for v1.

---

## 6. Lab intake model

## 6.1 User-facing entry flow

The user opens their profile and selects something like:

- `Upload lab result`
- or `Add analysis result`

Then the user is guided through a structured wizard.

### 6.2 Wizard flow concept

Suggested flow:

1. choose panel or marker from known list;
2. enter sample/report date;
3. enter numeric value;
4. select or confirm unit;
5. optionally enter lab-provided reference min/max;
6. save result;
7. continue with next marker or finish report.

### 6.3 Why marker-first entry is important

Because the system must know exactly which markers it understands and how to compare them across time.

This also prevents free-form chaos.

---

## 7. Marker library model

The system should work from a **known marker library**.

### 7.1 Why marker library is needed

The product must know:

- marker identity;
- canonical code;
- accepted units;
- comparison rules;
- whether the marker is relevant for hormone health, blood viscosity, lipid status, liver stress, etc.;
- whether it should influence specialist triage.

### 7.2 Marker library categories

MVP should support at least these categories.

#### A. Male hormone markers

Examples:

- total testosterone;
- free testosterone;
- LH;
- FSH;
- prolactin;
- SHBG;
- estradiol;
- DHEA-S;
- free androgen index if appropriate.

#### B. Hematology / blood thickness risk markers

Examples:

- hematocrit;
- hemoglobin;
- red blood cell count.

#### C. Lipid profile markers

Examples:

- total cholesterol;
- LDL;
- HDL;
- triglycerides.

#### D. Liver-related markers

Examples:

- ALT;
- AST;
- GGT (later if desired).

#### E. Glucose / metabolic markers

Examples:

- fasting glucose;
- insulin later;
- HbA1c later.

#### F. Growth-hormone-related monitoring markers (later or optional early)

Examples:

- IGF-1;
- fasting glucose;
- insulin-related markers later.

### 7.3 Marker library rule

Only markers with known product semantics should be available in the structured intake wizard.

The product must not pretend to interpret arbitrary free-form labs that it does not model.

---

## 8. Lab panel / package model

The product should support the idea of predefined lab panels.

### 8.1 Why panels matter

Panels help users avoid random, incomplete testing.

They also help the product guide users toward coherent monitoring.

### 8.2 Panel concept

A panel is a named set of markers grouped for a monitoring purpose.

Examples of product-level panel groups:

- male hormone status;
- androgen deficiency baseline;
- protocol safety / blood thickness;
- lipid monitoring;
- liver monitoring;
- growth-hormone related monitoring later.

### 8.3 External lab packages as guidance, not hard dependence

The system may later map known external lab packages (for example from Synevo or similar labs) into internal panels.

But internally the product should still reason in terms of:

- markers;
- panel templates;
- monitoring goals.

Not in terms of one external provider’s marketing packaging.

---

## 9. Lab report model

A lab report in CycleSync should be a structured object containing one or more marker values taken on a specific date.

### 9.1 Core properties

A report should contain:

- report date;
- upload/entry date;
- linked user;
- linked active protocol if relevant;
- one or more marker values;
- optional source/provider metadata;
- optional note.

### 9.2 Important rule

The date of sampling/report matters more than the date of data entry.

The system must preserve both.

### 9.3 Report grouping rule

Multiple markers entered in one user session may belong to one logical report object if they share the same sampling date/context.

---

## 10. Units and reference ranges

### 10.1 Unit-aware storage is mandatory

The system must not store values as naked numbers only.

Each marker entry must preserve:

- numeric value;
- unit;
- optional lab reference range;
- optional provider-specific reference text.

### 10.2 Why reference ranges must be user-enterable

Different labs may use different reference intervals.

If the user has the lab’s own reference range, the product should allow entering it explicitly.

This avoids pretending there is one universal lab “norm” across providers.

### 10.3 Why this matters for AI and specialist review

AI and specialist workflows become much stronger when the record shows:

- the measured value;
- the unit;
- the lab’s own reference interval;
- the protocol context;
- the previous values.

---

## 11. Manual entry wizard design principles

### 11.1 Marker selection must come from known list

The user should not type arbitrary marker names in the MVP core flow.

Instead they should:

- select marker from list;
- then enter value.

### 11.2 Minimal user effort, maximal data clarity

The wizard should be short and structured.

### 11.3 Good default flow

For each marker:

- choose marker;
- enter report date;
- enter value;
- confirm unit;
- optionally enter reference min/max;
- save.

### 11.4 Session-based entry

The user should be able to add multiple markers into one report session before saving the whole report.

---

## 12. Historical comparison model

CycleSync should treat labs not as isolated snapshots, but as history.

### 12.1 Why history matters

The system’s value comes from tracking:

- what changed;
- when it changed;
- whether the change happened during a specific protocol phase;
- whether adherence was strong or broken during that period.

### 12.2 Comparison dimensions

A marker may be compared against:

- previous report value;
- baseline value;
- previous value under same protocol;
- previous value before protocol start.

### 12.3 Historical truth rule

The product must never lose earlier marker values just because a newer report exists.

---

## 13. AI triage role

AI is a **triage and interpretation assistant**, not the center of product truth.

### 13.1 AI responsibilities

AI should:

- consume structured marker data;
- compare current values to historical values;
- consider protocol context;
- consider adherence context if relevant;
- surface risk flags;
- produce concise preliminary summaries;
- build clean context for specialist escalation.

### 13.2 AI should not do

AI should not:

- replace structured lab data;
- invent values from screenshots;
- become the sole decision-maker;
- overwrite protocol truth;
- act as if it is a doctor.

---

## 14. AI triage output model

AI triage output should be structured, not just a blob of chatty text.

### 14.1 Minimum output components

- summary text;
- marker-level observations;
- trend observations;
- risk flags;
- severity level or urgency tier;
- specialist escalation suggestion if needed.

### 14.2 Example output classes

#### Informational

No major concern, monitor over time.

#### Attention-needed

Meaningful change or pattern detected, should be watched.

#### Escalate-to-specialist

The case should be reviewed by a human expert.

### 14.3 Important rule

AI output must remain traceable to structured source data.

---

## 15. Specialist escalation model

### 15.1 Why specialist flow exists

There are cases where:

- structured monitoring is not enough;
- AI summary is useful but not sufficient;
- a real specialist must review the protocol, adherence and lab history together.

### 15.2 Specialist flow principle

The user should not have to rebuild their case manually in chat.

The system should package the case automatically.

### 15.3 What a specialist should receive

A specialist case should include:

- user profile basics;
- current protocol;
- active or latest pulse plan;
- adherence summary;
- recent lab reports;
- AI triage summary;
- report chronology.

This is a major value point of the product.

---

## 16. Expert case assembly

### 16.1 Case assembly rule

An expert case must be assembled from linked structured objects, not by copy-pasting random chat fragments.

### 16.2 Core case components

A case may contain:

- protocol snapshot;
- pulse-plan snapshot;
- adherence snapshot;
- selected lab reports;
- AI assessment links;
- user question/intent;
- specialist responses.

### 16.3 Why structured assembly matters

Because the specialist must work with:

- comparable data;
- time context;
- protocol context;
- discipline context.

Without that, the whole thing collapses into human inbox chaos.

---

## 17. Relationship to protocol and adherence truth

Labs, AI and expert cases are downstream of the execution system.

### 17.1 Labs without protocol context are weaker

A lab report alone tells less than:

- lab report + active protocol;
- lab report + adherence quality;
- lab report + time since protocol start.

### 17.2 Broken protocol context matters

If the reminder/adherence system has flagged the protocol as broken, this must be visible in the monitoring layer.

Otherwise the specialist may interpret numbers as if the user followed the plan, when in fact the plan already collapsed.

---

## 18. Optional raw attachments

### 18.1 MVP recommendation

Raw file upload should be optional and secondary.

It may be supported later as:

- archive/reference attachment;
- specialist-side evidence;
- future OCR assist input.

### 18.2 Important rule

Even if attachments are later allowed, the **primary truth must remain structured marker input**.

---

## 19. Suggested marker and panel strategy for MVP

### 19.1 MVP marker strategy

Start with a curated set of markers that the product can actually compare and interpret.

### 19.2 MVP panel strategy

Recommended internal product panels:

- male hormone baseline;
- male hormone follow-up;
- protocol safety baseline;
- blood thickness / hematology check;
- lipid profile check;
- liver check;
- optional GH-related check later.

### 19.3 Why internal panels beat external dependence

External provider packages may change.
The product should remain stable around internal marker logic.

---

## 20. Search and UX relation

This subsystem should remain secondary to the search-first/product-first UX.

### 20.1 Labs should not steal the home screen

Search and protocol building remain the primary front-door experience.

### 20.2 Labs are profile/workflow tools

The likely user path is:

- find compounds;
- build protocol;
- execute protocol;
- add labs later from profile/history.

### 20.3 Why this matters

Because if labs become the main front-door mode, the product risks drifting away from its core identity.

---

## 21. Analytics for labs and expert cases

The system should track at least:

- number of lab reports added;
- panel usage;
- marker completeness;
- AI assessments created;
- escalation rate to specialist;
- time from lab entry to specialist case;
- most common risk flag categories.

These are second-layer product quality signals.

---

## 22. Data model implications

The data model should support entities such as:

- `LabReport`
- `LabMarkerValue`
- `LabAttachment` (optional/secondary)
- `AIAssessment`
- `RiskFlag`
- `TrendObservation`
- `ExpertCase`
- `ExpertCaseLink`
- `ExpertMessage`

### 22.1 Important modeling rule

Do not flatten all monitoring information into one giant generic “analysis” table.

Structured separation is necessary for:

- historical comparison;
- AI input quality;
- specialist review;
- future panel logic.

---

## 23. Guardrails

This subsystem must avoid the following mistakes.

### 23.1 OCR-first trap

Do not make OCR/media parsing the primary MVP path.

### 23.2 File fetish

Do not treat uploaded documents as more important than structured numeric truth.

### 23.3 AI-as-doctor trap

Do not position AI as the final authority.

### 23.4 Marker chaos

Do not allow free-form marker names everywhere if the product cannot interpret them consistently.

### 23.5 Detached specialist inbox

Do not let specialist handling become unstructured chat without protocol/adherence/lab context.

### 23.6 Monitoring detached from execution

Do not interpret labs while ignoring whether the user actually followed the protocol.

---

## 24. Recommended future dependent documents

This document should feed the creation of:

- `docs/61_marker_library.md`
- `docs/62_internal_lab_panels.md`
- `docs/63_ai_triage_rules.md`
- `docs/64_expert_case_workflow.md`
- `docs/70_analytics.md`

These names are recommendations and may change.

---

## 25. Final statement

CycleSync labs and expert subsystem must be built on one core idea:

> **The system should work with precise structured marker data, not with OCR chaos.**

That allows the product to:

- compare values over time;
- understand protocol context;
- understand adherence context;
- give AI clean inputs;
- and assemble a specialist-ready case without manual chaos.

If this layer is built correctly, CycleSync becomes not just a calculation tool, but a coherent monitoring and escalation system.  
If built incorrectly, it degenerates into screenshots, parsing errors and AI pretending to be clever over bad data.
