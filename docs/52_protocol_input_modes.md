# CycleSync — Protocol Input Modes

## 1. Purpose

This document fixes the missing product layer between:

- **what the user wants to solve**, and
- **how the mathematical engine lays out pulses**.

The project already has calculation strategies such as:

- `unified_rhythm`
- `layered_pulse`
- `golden_pulse`

But these are **not input modes**. They are **layout strategies**.

The system must first understand **what kind of task the user is giving it**, and only then choose how to calculate the pulse schedule.

---

## 2. Core distinction

CycleSync must separate two layers:

### 2.1. Protocol input mode

Defines **what the user gives the system**.

Examples:
- "I picked 4 compounds, suggest a balanced pulse plan"
- "I already know how much of each compound I want, smooth it"
- "I need 1500 mg total per week, distribute it"
- "I only have these exact leftovers at home, build the least bad schedule"

### 2.2. Pulse layout strategy

Defines **how the system mathematically lays out the schedule** once the input mode is known.

Strategies already aligned with the engine:
- `unified_rhythm`
- `layered_pulse`
- `golden_pulse`

Important rule:

> Input mode and layout strategy are different things and must not be mixed.

---

## 3. Required user-facing protocol modes

CycleSync should support **4 protocol modes**.

Three are mainstream. One is paid and advanced.

---

## 4. Mode A — Auto Pulse

### 4.1. Product meaning

User says:

> "I selected these compounds. Build me the most balanced pulse plan you can."

This is the default mass-market mode.

### 4.2. User input

User selects:
- compounds/products
- duration
- optional max injection volume per event
- optional max injections per week
- optional preferred layout strategy

User does **not** manually set per-product mg/week.

### 4.3. What the system does

The engine:
- reads half-life and pharmacology metadata from catalog
- reads internal default guidance
- derives product weights
- distributes the schedule automatically
- optimizes for a steady blood-level profile

### 4.4. Use case

Best for:
- beginners
- users who do not know how to allocate compounds
- users who want a mathematically sane default proposal

### 4.5. Access policy

Can be:
- free preview with limits, or
- paid calculation access

Commercial policy may vary.

---

## 5. Mode B — Stack Smoothing

### 5.1. Product meaning

User says:

> "I already know what stack composition I want. Don’t invent my stack. Just smooth it and pulse it correctly."

This mode maps directly to the type of scenario represented by the earlier sample calculation.

### 5.2. User input

User selects:
- compounds/products
- per-product target values
- duration
- optional max injection volume per event
- optional max injections per week
- optional preferred layout strategy

Per-product targets may be expressed as:
- mg/week per selected product, or
- planned ml pattern if supported later

For MVP, `mg/week per product` is the cleanest form.

### 5.3. What the system does

The engine:
- does **not** redistribute the stack composition from scratch
- uses the user/expert-provided per-product targets
- calculates the smoothest possible pulse layout
- checks whether the result violates volume/frequency constraints
- returns warnings if the desired stack cannot be smoothed cleanly

### 5.4. Use case

Best for:
- advanced users
- trainer-guided stacks
- sports physician / rehab specialist use
- validating a manually designed stack against a mathematical pulse model

### 5.5. Access policy

Recommended as:
- normal product mode, not hidden
- can be free or paid depending commercial policy

This mode is strategically important because it directly answers:

> "Doctors and coaches usually set this by eye. We want the machine to smooth it mathematically."

---

## 6. Mode C — Total Target

### 6.1. Product meaning

User says:

> "I need X mg total per week. I picked the compounds. Distribute the load for me."

This is the current strongest implemented logic direction in the codebase.

### 6.2. User input

User selects:
- compounds/products
- total weekly target mg
- duration
- optional max injection volume per event
- optional max injections per week
- optional preferred layout strategy

### 6.3. What the system does

The engine:
- uses guidance metadata
- derives weighted allocation across selected compounds
- computes the pulse layout
- warns when data quality is weak or guidance bands are exceeded

### 6.4. Use case

Best for:
- advanced users
- bodybuilding / mass-gain planning
- users who already know the total intended load

### 6.5. Access policy

Recommended as:
- advanced mode
- paid or partially gated mode depending commercial policy

---

## 7. Mode D — Inventory-Constrained

### 7.1. Product meaning

User says:

> "I already have this exact stash at home. I am not buying more. What is the most stable protocol I can build from it?"

This mode is real-world and important, but mathematically ugly.

### 7.2. User input

User selects:
- compounds/products
- quantity on hand for each product
- duration or desired horizon
- optional max injection volume per event
- optional max injections per week
- optional preferred layout strategy

### 7.3. What the system does

The engine:
- treats stock quantity as a hard constraint
- tries to keep the blood level as even as possible
- may produce degraded solutions
- must show explicit compromises and warnings

### 7.4. Important rule

This mode does **not** promise ideal mathematics.

It promises:

> the least bad stable solution possible under stock constraints.

### 7.5. Access policy

This mode should be:
- **paid**
- clearly labeled as advanced
- explicitly warning-heavy

Reason:
- it is harder to calculate well
- it can force ugly compromises
- it must not be positioned as the normal clean product path

---

## 8. Input modes vs layout strategies matrix

| Input mode | What user fixes | What engine decides | Typical user |
|---|---|---|---|
| Auto Pulse | selected compounds + limits | composition weighting + pulse plan | beginner |
| Stack Smoothing | per-product targets + limits | pulse plan only | advanced |
| Total Target | total weekly mg + limits | per-product allocation + pulse plan | advanced/pro |
| Inventory-Constrained | actual stock + limits | best possible pulse plan under stock limits | paid advanced |

Layout strategy is a second layer and can apply inside each mode where mathematically valid:
- `unified_rhythm`
- `layered_pulse`
- `golden_pulse`

---

## 9. Course lifecycle model

The system must clearly distinguish:

### 9.1. Calculated protocols

These are drafts / previews / saved scenarios.

User may calculate many of them:
- for comparison
- for planning later
- for "just looking"

These must be stored as **non-active protocol scenarios**.

### 9.2. Active protocol

This is the protocol that the user actually started.

Rules:
- only **one active protocol** per user by default
- starting a protocol triggers reminder/tracking logic
- a calculated protocol is not active until user explicitly presses **Start**

### 9.3. Suggested statuses

For protocol objects:
- `draft`
- `calculated`
- `saved`
- `ready_to_start`
- `active`
- `paused`
- `completed`
- `cancelled`
- `archived`

### 9.4. Important product rule

> Calculation and activation are different actions.

User must be able to:
- calculate now,
- buy later,
- do labs first,
- start only when ready.

That is expected and correct.

---

## 10. Start / activation semantics

### 10.1. What Start means

When user presses **Start protocol**:
- protocol becomes active
- reminder materialization begins
- adherence tracking begins
- this is the moment where execution layer starts to matter

### 10.2. Access policy

Recommended:
- viewing calculations may be partially free or preview-tier
- **Start protocol** should be gated by paid execution access

Because Start means:
- reminders
- tracking
- adherence/integrity monitoring
- operational value, not just calculation

---

## 11. Packaging / quantity / "how much do I need to buy"

This is a missing but necessary capability.

After calculation, the system should be able to estimate:
- total mg required per product over protocol duration
- total ml required per product over protocol duration
- package count required

### 11.1. For injectables

Need catalog fields such as:
- package type (`vial`, `ampoules`, `kit`)
- volume per vial / ampoule
- ampoules per pack
- concentration mg/ml

Then system can compute:
- total ml needed
- total packs needed
- remaining leftover estimate

### 11.2. For tablets / oral compounds

Need catalog support for:
- mg per tablet/capsule
- tablets/capsules per pack
- package count required

Then system can compute:
- total mg needed
- total tablets needed
- total packs needed

### 11.3. Why this matters

Because real users think in:
- "How many vials do I need?"
- "Will what I already have be enough?"
- "Can I even start this protocol now?"

This is not cosmetic. It is core planning utility.

---

## 12. Product gap identified

At the moment, the system is strongest in **Mode C (Total Target)**.

But the original product vision clearly requires at least:
- **Mode A (Auto Pulse)**
- **Mode B (Stack Smoothing)**
- **Mode D (Inventory-Constrained, paid)**

So the real gap is not that "the system cannot calculate".

The real gap is:

> the system does not yet expose all the correct protocol input modes as first-class product behavior.

---

## 13. Recommended implementation order

### Priority 1
Add explicit `protocol_input_mode` to domain and flow.

Suggested enum:
- `auto_pulse`
- `stack_smoothing`
- `total_target`
- `inventory_constrained`

### Priority 2
Implement **Stack Smoothing** first.

Reason:
- it closes the gap between manual doctor/trainer plans and the mathematical engine
- it matches the original product promise most directly

### Priority 3
Implement **Auto Pulse** cleanly as default user mode.

### Priority 4
Implement **Inventory-Constrained** as paid advanced mode.

---

## 14. Final statement

CycleSync should not be positioned as a single calculator.

It should be positioned as:

> a protocol design and execution system with multiple mathematically distinct planning modes.

That is what makes it useful to:
- beginners,
- advanced users,
- sports physicians,
- rehab specialists,
- users who already know their stack,
- users who only know their inventory,
- users who need reminders, labs, AI triage and specialist consultation on top of the math.

The product idea is sound.

The next step is to formalize the missing input modes and wire them into the protocol flow.
