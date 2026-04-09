# CycleSync Marker Library

> Marker library document for **CycleSync**.

---

## 1. Purpose of this document

This document defines the marker library of CycleSync.

Its goals are to:

- formalize which laboratory markers the product understands;
- define marker categories and product relevance;
- define canonical naming and unit rules;
- define which markers belong to structured manual entry in MVP;
- prepare the foundation for lab panels, AI triage and specialist case assembly.

This document is **not**:

- a medical guideline;
- a treatment manual;
- a full clinical knowledge base;
- a provider-specific lab catalog.

Those belong elsewhere.

---

## 2. Why marker library must exist explicitly

CycleSync uses **structured manual lab entry**.

That means the product must know:

- which markers are supported;
- how they are named internally;
- which units are accepted;
- how they should be compared over time;
- which domain of monitoring they belong to;
- whether they matter for hormone balance, blood thickness, lipids, liver stress, metabolic status or GH-related monitoring.

Without an explicit marker library, the product drifts into:

- free-text chaos;
- inconsistent naming;
- broken comparisons;
- weak AI triage;
- confused specialist workflows.

---

## 3. Core marker-library principle

The marker library must be **product-first, structured and opinionated**.

This means:

- users select known markers from a list;
- markers have stable internal codes;
- units are controlled;
- the product does not pretend to interpret arbitrary unknown lab data in MVP;
- unsupported markers may exist later, but they do not enter the core structured flow until modeled.

---

## 4. Marker model

Each marker in CycleSync should conceptually include at least:

- `marker_code` — stable internal identifier
- `display_name` — human-readable name
- `aliases` — optional alternative names
- `category_code` — hormone / hematology / lipid / liver / metabolic / GH-related / other
- `accepted_units` — one or more supported units
- `default_unit` — preferred unit
- `is_active` — whether supported in current product flow
- `is_mvp_supported` — whether available in MVP manual-entry wizard
- `comparison_mode` — how historical comparison is handled conceptually
- `notes` — optional internal notes

---

## 5. Marker categories

CycleSync should organize markers into clear categories.

### 5.1 Male hormone markers

These are core markers for hormone state, androgen balance and protocol-related endocrine monitoring.

### 5.2 Hematology / blood thickness markers

These are used to track blood thickness / viscosity-related risk signals.

### 5.3 Lipid markers

These reflect lipid profile changes and cardiovascular risk context.

### 5.4 Liver-related markers

These track potential liver stress or related biochemical changes.

### 5.5 Metabolic markers

These help track glucose/metabolic status.

### 5.6 GH-related markers

These help monitor the broader metabolic/hormonal context relevant when somatotropin-related monitoring is needed.

### 5.7 Later / extended markers

A future category for markers not required in MVP but potentially valuable later.

---

## 6. MVP marker library scope

The MVP should support a curated marker set, not an endless clinical encyclopedia.

The product should start with the markers it can:

- store cleanly;
- compare over time;
- use in AI triage;
- surface to specialist workflows meaningfully.

Below is the recommended initial marker library.

---

## 7. Male hormone marker set (MVP)

### 7.1 Total Testosterone

- `marker_code`: `testosterone_total`
- `display_name`: Total Testosterone
- Category: male_hormones
- MVP support: yes
- Expected role: core hormone baseline and follow-up marker

### 7.2 Free Testosterone

- `marker_code`: `testosterone_free`
- `display_name`: Free Testosterone
- Category: male_hormones
- MVP support: yes
- Expected role: active hormone availability context

### 7.3 SHBG

- `marker_code`: `shbg`
- `display_name`: SHBG
- Category: male_hormones
- MVP support: yes
- Expected role: binding/availability context for testosterone interpretation

### 7.4 LH

- `marker_code`: `lh`
- `display_name`: LH
- Category: male_hormones
- MVP support: yes
- Expected role: pituitary/testicular axis context

### 7.5 FSH

- `marker_code`: `fsh`
- `display_name`: FSH
- Category: male_hormones
- MVP support: yes
- Expected role: reproductive axis context

### 7.6 Prolactin

- `marker_code`: `prolactin`
- `display_name`: Prolactin
- Category: male_hormones
- MVP support: yes
- Expected role: sexual function / endocrine side-effect context

### 7.7 Estradiol

- `marker_code`: `estradiol`
- `display_name`: Estradiol
- Category: male_hormones
- MVP support: yes
- Expected role: estrogen balance context

### 7.8 DHEA-S

- `marker_code`: `dhea_s`
- `display_name`: DHEA-S
- Category: male_hormones
- MVP support: yes
- Expected role: broader androgen/adrenal context

### 7.9 Free Androgen Index (optional MVP / strong candidate)

- `marker_code`: `free_androgen_index`
- `display_name`: Free Androgen Index
- Category: male_hormones
- MVP support: optional but recommended if product panels include it

---

## 8. Hematology / blood-thickness marker set (MVP)

### 8.1 Hematocrit

- `marker_code`: `hematocrit`
- `display_name`: Hematocrit
- Category: hematology
- MVP support: yes
- Expected role: blood thickness / viscosity-related risk context

### 8.2 Hemoglobin

- `marker_code`: `hemoglobin`
- `display_name`: Hemoglobin
- Category: hematology
- MVP support: yes

### 8.3 Red Blood Cell Count

- `marker_code`: `rbc`
- `display_name`: RBC
- Category: hematology
- MVP support: yes

Later extensions may include other CBC markers if needed, but MVP should keep the structured focus clear.

---

## 9. Lipid marker set (MVP)

### 9.1 Total Cholesterol

- `marker_code`: `cholesterol_total`
- `display_name`: Total Cholesterol
- Category: lipids
- MVP support: yes

### 9.2 LDL Cholesterol

- `marker_code`: `cholesterol_ldl`
- `display_name`: LDL Cholesterol
- Category: lipids
- MVP support: yes

### 9.3 HDL Cholesterol

- `marker_code`: `cholesterol_hdl`
- `display_name`: HDL Cholesterol
- Category: lipids
- MVP support: yes

### 9.4 Triglycerides

- `marker_code`: `triglycerides`
- `display_name`: Triglycerides
- Category: lipids
- MVP support: yes

---

## 10. Liver-related marker set (MVP)

### 10.1 ALT

- `marker_code`: `alt`
- `display_name`: ALT
- Category: liver
- MVP support: yes

### 10.2 AST

- `marker_code`: `ast`
- `display_name`: AST
- Category: liver
- MVP support: yes

### 10.3 GGT (recommended but optional for MVP)

- `marker_code`: `ggt`
- `display_name`: GGT
- Category: liver
- MVP support: optional but recommended as early extension

---

## 11. Metabolic marker set (MVP)

### 11.1 Fasting Glucose

- `marker_code`: `glucose_fasting`
- `display_name`: Fasting Glucose
- Category: metabolic
- MVP support: yes

### 11.2 HbA1c (optional but strong candidate)

- `marker_code`: `hba1c`
- `display_name`: HbA1c
- Category: metabolic
- MVP support: optional but useful

### 11.3 Insulin (later / optional early)

- `marker_code`: `insulin_fasting`
- `display_name`: Fasting Insulin
- Category: metabolic
- MVP support: optional later depending on panel scope

---

## 12. GH-related marker set

This category becomes more important when the product expands to stronger GH-related monitoring.

### 12.1 IGF-1

- `marker_code`: `igf1`
- `display_name`: IGF-1
- Category: gh_related
- MVP support: optional but recommended if GH use cases are expected early

### 12.2 Fasting Glucose

Already included in metabolic markers, but relevant here too.

### 12.3 Insulin-related markers later

These can be added when GH-focused panels are expanded.

---

## 13. Unit strategy

### 13.1 Why unit control matters

The same marker may appear in different units across labs.

If units are not controlled, the product cannot compare values safely.

### 13.2 Accepted unit principle

Each marker must define:

- one preferred/default unit;
- one or more accepted units if real-world lab variation is common.

### 13.3 MVP recommendation

In MVP, the system should:

- allow only known units per marker;
- require the user to choose/confirm the unit;
- store the raw entered unit;
- avoid automatic conversion unless conversion rules are explicitly modeled and tested.

### 13.4 Important rule

Do not silently convert units if the conversion logic is not explicitly built and trustworthy.

---

## 14. Reference ranges

### 14.1 Product rule

The user should be allowed to enter lab-provided reference ranges if they are available on the source report.

### 14.2 Why reference ranges matter

Different labs may use different reference intervals.

Allowing user-entered lab references preserves context and prevents the product from pretending that one universal lab reference exists everywhere.

### 14.3 Important distinction

The product may later have its own internal interpretation logic, but the **lab-provided range** should still be stored when entered.

---

## 15. Marker aliases

### 15.1 Why aliases matter

The same marker may appear under different visible names depending on the lab or language.

### 15.2 Marker alias principle

Marker library should support aliases for:

- different language spellings;
- abbreviations;
- provider-specific wording;
- common shorthand.

### 15.3 Important rule

Aliases must map to a single stable internal `marker_code`.

---

## 16. Marker comparison semantics

Different markers may be compared differently across time.

### 16.1 Comparison modes

Conceptual comparison modes may include:

- raw delta over time;
- baseline vs current;
- previous-report delta;
- protocol-start vs current;
- threshold-sensitive trend observation.

### 16.2 Why comparison mode matters

The product must know not just how to store a marker, but how to reason about historical movement later.

---

## 17. Marker library and internal panels

The marker library is the building block for internal lab panels.

Examples:

- male hormone baseline panel;
- male hormone follow-up panel;
- protocol safety panel;
- hematology check;
- lipid profile panel;
- liver panel;
- GH-related monitoring panel later.

The panel system should reference marker codes from this library rather than re-invent marker definitions inside each panel.

---

## 18. MVP support rule

A marker may exist in the library but still be flagged as:

- active and supported in MVP;
- defined but hidden until later;
- reserved for future specialist flow.

This allows the library to grow without bloating the first-release user wizard.

---

## 19. Data model implications

The marker library should later map into entities/tables such as:

- `markers`
- `marker_aliases`
- `marker_units`
- `marker_categories`
- `panel_marker_links`

This document does not lock the final table design, but it defines the conceptual model.

---

## 20. Guardrails

The marker-library subsystem must avoid the following mistakes.

### 20.1 Free-text lab chaos

Do not let users type arbitrary marker names in the main MVP structured flow.

### 20.2 Unit blindness

Do not store naked numbers without unit context.

### 20.3 Alias drift

Do not allow multiple marker identities to emerge for the same lab concept.

### 20.4 Over-expansion too early

Do not turn the MVP marker library into a giant medical encyclopedia before the core product validates.

### 20.5 Under-modeling core markers

Do not omit the obvious hormone / hematology / lipid / liver / metabolic markers that specialists actually need for context.

---

## 21. Recommended next dependent documents

This marker-library document should feed the creation of:

- `docs/62_internal_lab_panels.md`
- `docs/63_ai_triage_rules.md`
- `docs/64_expert_case_workflow.md`

These names are recommendations and may change.

---

## 22. Final statement

CycleSync must not work with vague “analysis text”.
It must work with a curated marker library built around:

- stable internal marker codes;
- known categories;
- controlled units;
- optional lab-specific reference ranges;
- structured comparison across time.

This is what allows labs, AI triage and specialist workflows to operate on clean truth instead of spreadsheet-style chaos.
