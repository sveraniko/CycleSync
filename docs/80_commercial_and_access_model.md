# CycleSync Commercial and Access Model

> Commercial structure, access control and feature monetization document for **CycleSync**.

---

## 1. Purpose of this document

This document defines the commercial and access model of CycleSync.

Its goals are to:

- formalize how users gain access to the product;
- define the difference between access gating and feature gating;
- define the free vs paid usage layers;
- define monetization logic for reminders, adherence and specialist consultations;
- define the role of access keys, entitlements and later subscriptions;
- ensure monetization does not distort the core product architecture.

This document is **not**:

- a payment provider integration spec;
- a legal billing document;
- a marketing copy document;
- a BI dashboard spec.

Those should be defined separately later.

---

## 2. Core commercial principle

CycleSync should **not** monetize like a locked black box where the user must pay before seeing any value.

The correct principle is:

> **Free entry, paid execution, paid premium guidance.**

This means:

- users should be able to enter the product and feel its value;
- the system should monetize the operational value layer, not just the login itself;
- specialist time must always be treated as a premium paid service.

---

## 3. Why hard ENV-only access is the wrong long-term model

Using environment-based hard access control may be useful for:

- closed alpha testing;
- developer-only deployments;
- invitation-only prototype rounds.

But as a long-term commercial model it is weak because it:

- does not scale well;
- does not support flexible user segmentation;
- does not support clean paid upgrades;
- does not support entitlement analytics well;
- creates unnecessary friction before value is demonstrated.

Therefore `env`-only access may exist temporarily for testing, but must not define the product’s commercial architecture.

---

## 4. Core distinction: Access vs Monetization

CycleSync must distinguish between:

### 4.1 Access control

Who is allowed to enter the product at all.

### 4.2 Feature monetization

Which product capabilities are available for free vs paid tiers.

### 4.3 Why this distinction matters

If these two are collapsed into one crude gate, the product becomes harder to test, harder to sell and harder to evolve.

---

## 5. Recommended high-level model

The recommended commercial model for CycleSync is:

1. **Free entry layer**
2. **Paid execution layer**
3. **Paid specialist layer**
4. **Later subscription / package layer**

This structure matches the actual product value curve.

---

## 6. Free entry layer

The free layer should allow users to feel the core product without granting unlimited operational value.

### 6.1 Recommended free capabilities

Free users may be allowed to:

- enter the bot;
- search compounds;
- open compound cards;
- add compounds to draft;
- build a basic draft;
- maybe run one demo calculation or one limited plan preview;
- see the general product value before paying.

### 6.2 Why free search matters

Search is the front door of CycleSync.
If users cannot test search and draft flow, the product asks for trust before demonstrating competence.

That is a bad commercial trade in a niche where trust matters.

### 6.3 Recommended free limits

Possible free constraints:

- one full calculation only;
- limited number of draft saves;
- no active reminders;
- no long-term protocol history;
- no specialist escalation;
- limited AI layer or none.

---

## 7. Paid execution layer

This is the first core monetization layer and likely the strongest recurring value layer.

### 7.1 What this layer means

The user pays not just for calculation, but for **living protocol execution over time**.

### 7.2 Recommended paid execution features

Paid execution should unlock:

- repeated calculations;
- active protocol management;
- reminders;
- adherence tracking;
- broken-protocol detection;
- protocol history;
- pulse-plan continuity over time;
- maybe advanced preset access later.

### 7.3 Why reminders belong here

Reminders in CycleSync are not generic push notifications.
They are:

- discipline automation;
- execution support;
- adherence capture;
- protocol health logic.

This is premium operational value.

### 7.4 Product wording truth

A free user can calculate.
A paid user can **execute and maintain** the protocol with system support.

That is a clean and honest commercial distinction.

---

## 8. Paid specialist layer

This layer monetizes human expertise.

### 8.1 Core rule

Human specialist review is always a paid service.

Because it consumes:

- professional time;
- review attention;
- case handling capacity;
- follow-up effort.

### 8.2 Recommended paid specialist triggers

Paid specialist access may be offered when the user:

- wants case review after AI triage;
- wants consultation on protocol/lab context;
- wants a human response instead of purely AI-preliminary output;
- wants deeper interpretation or follow-up.

### 8.3 Specialist layer may include

- one-off consultation payment;
- case package payment;
- later premium membership with included consults;
- priority queue later.

### 8.4 Important rule

Specialist value must not be hidden inside “free but unsustainable” product behavior.

---

## 9. Later subscription / package layer

After the core product is validated, CycleSync may grow into a richer commercial structure.

Possible future package layers:

- monthly subscription;
- protocol execution subscription;
- reminder-only subscription;
- AI monitoring package;
- specialist package bundles;
- men’s health package later;
- TRT / hormone-health follow-up package later.

These should be treated as later commercial expansion, not MVP dependency.

---

## 10. Access keys and controlled entry

### 10.1 Why access keys may still be useful

Although hard env gating is weak as a commercial model, **access keys** can still be useful.

They may support:

- invitation-only launch phases;
- partner-issued access;
- specialist-issued onboarding;
- promo access;
- paid access bundles later.

### 10.2 Access key role

An access key should be treated as a controlled entitlement mechanism, not as a crude developer switch.

### 10.3 What access keys may grant

An access key may grant:

- basic product entry;
- trial window;
- temporary execution access;
- bundled consultation access;
- partner plan activation.

### 10.4 Important rule

Access key logic should sit inside the commercial/access model, not in environment flags and manual deployment hacks.

---

## 11. Entitlement model

CycleSync should think in terms of **entitlements**.

An entitlement is a product-level permission granted to a user for a time or scope.

### 11.1 Example entitlement classes

- `bot_access`
- `calculation_access`
- `reminders_access`
- `adherence_access`
- `ai_triage_access`
- `expert_case_access`
- `priority_specialist_access` (later)

### 11.2 Why entitlements matter

They allow:

- clean feature gating;
- account upgrades/downgrades;
- trial logic;
- partner logic;
- access key activation;
- analytics on paid feature usage.

### 11.3 Time-bounded entitlements

Some entitlements may be:

- permanent;
- monthly;
- one-time use;
- case-based;
- trial-based.

---

## 12. Commercial product tiers (recommended)

The following tier model is recommended as a strategic starting point.

## 12.1 Tier A — Free / Explore

Purpose:

- let the user see real product value;
- reduce trust barrier;
- feed activation funnel.

Capabilities:

- search;
- open compound card;
- add to draft;
- maybe one calculation preview.

Restrictions:

- no continuous protocol execution;
- no reminders;
- no adherence history;
- no specialist access;
- limited or no AI triage.

## 12.2 Tier B — Execution

Purpose:

- monetize the discipline/execution layer.

Capabilities:

- repeated calculations;
- active protocol;
- reminders;
- adherence;
- broken-protocol detection;
- protocol history.

## 12.3 Tier C — Expert

Purpose:

- monetize specialist labor and high-trust guidance.

Capabilities:

- specialist case opening;
- specialist review;
- specialist reply / follow-up;
- optional AI triage included or enhanced.

## 12.4 Tier D — Future packages

Purpose:

- allow later bundling and specialization.

Examples:

- men’s health package;
- TRT package;
- advanced monitoring package;
- premium specialist bundle.

---

## 13. Recommended monetization path in MVP

### 13.1 What should likely remain free

- entry into the bot;
- search;
- product discovery through search;
- draft assembly;
- maybe one limited demonstration calculation.

### 13.2 What should be paid from the beginning

- reminders;
- adherence/discipline layer;
- specialist consultation;
- deeper premium execution support.

### 13.3 Why this is a strong MVP commercial model

It lets the user:

- understand the product;
- experience the core mechanic;
- then pay for real ongoing value.

That is more rational than charging for mere entry.

---

## 14. Paywall philosophy

CycleSync should use **value-aligned paywalls**, not random friction walls.

### 14.1 Good paywall moments

Examples:

- after first successful calculation preview;
- when the user tries to activate reminders;
- when the user tries to save an active long-running protocol;
- when the user wants specialist review.

### 14.2 Bad paywall moments

Examples:

- before the user has seen search quality;
- before the user understands draft flow;
- before any product value was demonstrated.

### 14.3 Product principle

Users should hit a paywall at the moment they feel the cost of not having the feature.

That is especially true for reminders and specialist support.

---

## 15. Reminder monetization strategy

### 15.1 Why reminders are commercially strong

Reminders are one of the strongest product monetization points because they:

- save mental bandwidth;
- reduce missed actions;
- preserve pulse-plan integrity;
- create habit dependence;
- are easy for users to understand as ongoing value.

### 15.2 Commercial framing

The system should frame reminders not as “notifications” but as:

- execution support;
- protocol discipline layer;
- real-world maintenance of the plan.

### 15.3 Recommended monetization policy

Reminders should be a paid feature or part of a paid execution tier.

---

## 16. AI layer monetization options

AI triage can be monetized later in multiple ways.

### 16.1 Possible models

- free limited summary;
- paid detailed interpretation;
- AI included in expert tier;
- AI included in premium monitoring package.

### 16.2 MVP recommendation

Do not make AI the first monetization pillar.

The stronger early monetization pillars are:

- reminders/execution;
- specialist consultation.

AI can strengthen monetization later but should not distort the core commercial logic early.

---

## 17. Consultation monetization strategy

### 17.1 Consultation is not a free support message

A consultation or specialist case consumes real professional labor.

### 17.2 Recommended payment structures

Possible payment structures:

- one case = one payment;
- packaged specialist review;
- subscription with included consultations later;
- priority queue add-on later.

### 17.3 Product rule

Consultation payment should be explicit and clean.
Do not bury it inside unclear “premium” promises.

---

## 18. Access and commercial analytics requirements

The analytics system must be able to answer:

- how many users enter for free;
- how many search and draft but never pay;
- how many convert after first calculation;
- how many unlock reminders;
- how many buy consultation;
- which paywall moment converts best;
- whether free users become paying users later.

That means the commercial model must emit clear events such as:

- `access_key_redeemed`
- `free_limit_reached`
- `paywall_seen`
- `execution_tier_purchased`
- `reminders_access_enabled`
- `consultation_checkout_started`
- `consultation_paid`

---

## 19. Data model implications

The commercial/access model should later map into entities such as:

- `AccessKey`
- `Entitlement`
- `EntitlementGrant`
- `FeatureGateRule`
- `CheckoutSession`
- `PaymentRecord`
- `CommercialPlan`
- `UserCommercialState`

### 19.1 Important rule

Do not entangle commercial state directly with protocol tables “for convenience”.

Commercial logic must remain a separate bounded context or at least a distinct module.

---

## 20. Architecture recommendation

### 20.1 Core product first, commercial layer separately modeled

The correct sequence is:

- build core product spine first;
- define commercial/access model alongside it;
- implement commercial gating as a distinct layer on top of product capabilities.

### 20.2 Why separate modeling matters

Because commercialization should not contaminate:

- pulse-engine logic;
- protocol truth;
- reminder semantics;
- lab semantics.

### 20.3 But do not postpone it too much

Commercial architecture should be modeled early even if fully implemented later.

Otherwise the product ends up retrofitting payment logic awkwardly into operational domains.

---

## 21. Guardrails

The commercial/access model must avoid the following mistakes.

### 21.1 ENV-as-business-model

Do not treat environment flags as the permanent access architecture.

### 21.2 Paywall-before-value

Do not demand payment before the user has seen enough product competence.

### 21.3 Free-everything illusion

Do not give away labor-intensive and retention-heavy features for free if they carry real operational cost.

### 21.4 Commercial-domain contamination

Do not mix payment/access truth into protocol or reminder core tables unnecessarily.

### 21.5 Specialist labor devaluation

Do not normalize unpaid specialist review as if it were free support noise.

### 21.6 Reminder undervaluation

Do not frame reminders as trivial notifications. They are one of the product’s main paid-value layers.

---

## 22. Recommended future dependent documents

This commercial/access model should feed the creation of:

- `docs/81_entitlement_model.md`
- `docs/82_payment_and_checkout.md`
- `docs/83_paywall_strategy.md`
- `docs/84_commercial_analytics.md`

These names are recommendations and may change.

---

## 23. Final statement

CycleSync should monetize through **value-aligned feature layers**, not through crude environment-level exclusion.

The strongest initial model is:

- **free entry and discovery**;
- **paid execution support** (especially reminders/adherence);
- **paid specialist guidance**;
- later subscriptions and packages.

This model matches the real product value curve and keeps the architecture honest.

If built correctly, the commercial layer will amplify the product.  
If built badly, it will either strangle adoption or turn the product into a confused paywall maze.
