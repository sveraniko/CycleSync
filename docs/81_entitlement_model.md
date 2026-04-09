# CycleSync Entitlement Model

> Entitlement and feature-access model document for **CycleSync**.

---

## 1. Purpose of this document

This document defines the entitlement model of CycleSync.

Its goals are to:

- formalize how user access rights are represented inside the product;
- distinguish identity, access, payment and feature availability;
- define entitlement types and scopes;
- define how access keys, plans and purchases grant capabilities;
- define time-bounded and usage-bounded rights;
- support commercial gating without contaminating core domain logic.

This document is **not**:

- a payment provider integration spec;
- a billing/legal document;
- a checkout UI spec;
- a pricing strategy memo.

Those should be defined elsewhere.

---

## 2. Why entitlements must exist explicitly

CycleSync is not a single flat-access product.
It has multiple value layers:

- free discovery/search;
- paid execution support;
- paid reminder/adherence layer;
- paid specialist consultations;
- later packages and premium bundles.

If feature access is implemented through:

- hardcoded `if premium` checks;
- environment flags;
- hand-edited user rows;
- vague plan names with no internal rights model,

then the product quickly becomes brittle, opaque and hard to evolve.

The entitlement model exists to prevent that.

---

## 3. Core entitlement principle

The central rule is:

> **Users do not merely “have a plan”. They hold explicit product entitlements that grant concrete capabilities.**

This means:

- payment is not the same as entitlement;
- access key is not the same as entitlement;
- user identity is not the same as entitlement;
- a plan/package may grant one or more entitlements;
- entitlements are the direct source of feature availability.

---

## 4. Conceptual layers

The access/commercial model should distinguish the following layers:

### 4.1 Identity layer

Who the user is.

Examples:

- `user_id`
- Telegram identity
- profile

### 4.2 Commercial layer

Why the user should receive some rights.

Examples:

- purchase
- access key
- promo grant
- specialist-issued access
- trial

### 4.3 Entitlement layer

What the user is actually allowed to do.

Examples:

- use reminders
- maintain active protocol execution
- open specialist case

### 4.4 Feature-gate layer

How the application checks and applies entitlement truth at runtime.

---

## 5. What an entitlement is

An entitlement is a structured grant of product capability.

It answers questions like:

- can this user calculate beyond the free limit;
- can this user enable reminders;
- can this user use adherence tracking;
- can this user open specialist cases;
- until when is that right valid;
- under what conditions does it expire.

Entitlements should be explicit, queryable and auditable.

---

## 6. Entitlement types

CycleSync should define explicit entitlement classes.

### 6.1 Core candidate entitlement types

#### `bot_access`

Allows basic entry into the product.

#### `calculation_access`

Allows full protocol calculation beyond free/demo limits.

#### `active_protocol_access`

Allows long-running operational execution of protocols, not just preview.

#### `reminders_access`

Allows reminder automation to function.

#### `adherence_access`

Allows full adherence tracking and related execution history.

#### `ai_triage_access`

Allows AI-generated preliminary assessment where monetized.

#### `expert_case_access`

Allows opening a paid specialist case.

#### `priority_specialist_access` (later)

Allows access to premium specialist lane or better SLA.

### 6.2 Future entitlement types

Later layers may include:

- `mens_health_module_access`
- `trt_package_access`
- `premium_monitoring_access`
- `bundle_access`

---

## 7. Entitlement scopes

An entitlement is not always binary/forever.
It may have a scope.

### 7.1 Time-bounded scope

Examples:

- 30 days of reminders
- monthly active execution access
- consultation access valid for 7 days

### 7.2 Usage-bounded scope

Examples:

- one extra calculation
- one specialist case opening
- one-time reminder unlock for limited period

### 7.3 Context-bounded scope

Examples:

- entitlement tied to one protocol;
- entitlement tied to one consultation case;
- entitlement tied to a specific package.

### 7.4 Unlimited scope

Examples:

- admin-granted internal access;
- permanent access for trusted partner/tester cohort.

---

## 8. Entitlement sources

An entitlement may originate from different commercial or operational sources.

### 8.1 Purchase source

A payment or plan purchase grants one or more entitlements.

### 8.2 Access key source

A redeemed key grants one or more entitlements.

### 8.3 Trial source

A time-limited trial grants temporary entitlements.

### 8.4 Manual/admin source

Later or internal use only:

- support grant;
- internal test access;
- specialist-issued allowance.

### 8.5 Promo/partner source

Partner collaborations or controlled launches may grant entitlements via a predefined rule set.

---

## 9. Access keys and entitlements

### 9.1 Why access keys still matter

Even though hard `env` access is not a product model, **access keys** remain useful.

They support:

- controlled launch waves;
- partner programs;
- specialist-issued onboarding;
- promo distribution;
- temporary unlocks.

### 9.2 Access key principle

An access key should not directly hardcode feature behavior.

Instead:

- key is redeemed;
- key resolves to one or more entitlement grants;
- entitlements become the runtime truth.

### 9.3 Why this matters

Because keys are just one source of rights.
The application should reason in entitlements, not in scattered key logic.

---

## 10. Plans and bundles

Commercial plans or bundles should be defined as **entitlement packages**.

### 10.1 Plan example concept

A plan may grant:

- `calculation_access`
- `active_protocol_access`
- `reminders_access`
- `adherence_access`

A specialist consultation purchase may grant:

- `expert_case_access`

A later premium package may grant:

- execution layer entitlements + AI triage + expert priority.

### 10.2 Important rule

A plan is a commercial wrapper.
Entitlements are the actual product rights.

---

## 11. Runtime feature-gate model

### 11.1 Feature checks must read entitlements

Feature availability in the app should be determined by entitlement truth.

Examples:

- before enabling reminders -> check `reminders_access`
- before opening paid specialist case -> check `expert_case_access`
- before unlimited recalculation -> check `calculation_access`

### 11.2 Why this matters

It keeps product gating:

- explicit;
- auditable;
- testable;
- decoupled from payment plumbing.

### 11.3 Feature-gate rule

The UI should still explain why a feature is blocked.
Entitlements should not result in silent dead buttons.

---

## 12. Expiration model

### 12.1 Why expiration matters

Not all access rights are permanent.

### 12.2 Expiration types

Entitlements may end because:

- time expires;
- usage quota is exhausted;
- manual revocation occurs;
- a trial ends;
- a specific case is closed or consumed.

### 12.3 Expiration behavior

When an entitlement expires:

- the right becomes inactive;
- related feature gates should reflect this;
- history of the entitlement must remain queryable.

### 12.4 Important rule

Expiration must not silently corrupt core domain truth.

Example:

- expiring `reminders_access` should stop reminders from being available, but should not delete protocol history.

---

## 13. Revocation model

### 13.1 Why revocation exists

The system must support explicit revocation in some cases.

Examples:

- refund/cancellation flows later;
- abuse or support intervention;
- mistaken grant;
- end of internal testing access.

### 13.2 Revocation rule

Revocation should:

- create a traceable state transition;
- preserve entitlement history;
- not mutate payment history silently.

---

## 14. Free-tier and entitlement relation

### 14.1 Free users are still users with a rights profile

Free access should not be implemented as “absence of all structure”.

Even free users may have implicit or explicit default rights such as:

- `bot_access`
- limited search access
- maybe limited calculation trial

### 14.2 Why free should still be modeled

Because the system must understand:

- who is free;
- what free users can do;
- when free limits are reached;
- when paywalls should trigger.

---

## 15. Trial model

### 15.1 Trial concept

A trial is a temporary entitlement grant, not a weird pseudo-plan.

### 15.2 Trial use cases

- temporary reminder access;
- limited execution period;
- launch cohort testing;
- partner onboarding.

### 15.3 Trial end behavior

When a trial ends:

- entitlement expires;
- feature gates reflect expiry;
- user is routed into the next commercial step.

---

## 16. Specialist access model

### 16.1 Why specialist access must be modeled explicitly

Specialist time is premium labor.
The system must not treat “contact specialist” as an unbounded casual action.

### 16.2 Recommended specialist access structure

A consultation purchase should grant:

- `expert_case_access`

Optionally later:

- `priority_specialist_access`
- multi-case package rights

### 16.3 Consumption rule

An entitlement may be consumed by opening a case if the commercial logic defines it that way.

---

## 17. Reminder/adherence monetization relation

### 17.1 Why these features need explicit rights

Reminders and adherence are not cosmetic extras.
They are a core monetized execution layer.

### 17.2 Recommended entitlements

To preserve clarity, the product may distinguish:

- `reminders_access`
- `adherence_access`
- maybe `active_protocol_access`

Depending on packaging strategy, these may be bundled or separate.

### 17.3 Why separate them conceptually even if bundled

Because later commercial flexibility becomes much easier if the rights model is clean from the start.

---

## 18. Entitlement lifecycle states

Suggested entitlement states:

- `active`
- `scheduled` (optional later)
- `expired`
- `revoked`
- `consumed` (for one-time rights)
- `superseded` (optional if replaced by another grant)

### 18.1 State meaning

#### `active`

The user currently holds the right.

#### `expired`

The time window ended.

#### `revoked`

The grant was intentionally withdrawn.

#### `consumed`

A one-time entitlement was used.

#### `superseded`

A newer entitlement replaced it where modeling requires that.

---

## 19. Data model implications

The entitlement model should later map into entities/tables such as:

- `CommercialPlan`
- `Entitlement`
- `EntitlementGrant`
- `AccessKey`
- `AccessKeyRedemption`
- `FeatureGateRule`
- `UserCommercialState`

### 19.1 Recommended conceptual roles

#### `Entitlement`

Defines the right type itself.

#### `EntitlementGrant`

Represents a concrete grant of that right to a user.

#### `CommercialPlan`

Defines a package or plan that issues one or more entitlement grants.

#### `FeatureGateRule`

Maps application features to required entitlements.

---

## 20. Event implications

The event catalog should support entitlement-related events such as:

- `access_key_redeemed`
- `entitlement_granted`
- `entitlement_expired`
- `entitlement_revoked`
- `free_limit_reached`
- `execution_tier_purchased`
- `consultation_paid`

These are important for analytics, auditability and operational troubleshooting.

---

## 21. Analytics implications

Analytics should be able to answer:

- which entitlements are granted most often;
- which expire unused;
- which convert best after free discovery;
- whether paid users actually use the features they unlocked;
- how access keys perform vs direct purchase;
- what happens after reminder entitlement expires.

Without a proper entitlement model, these questions become fuzzy and misleading.

---

## 22. Guardrails

The entitlement model must avoid the following mistakes.

### 22.1 Plan-as-right confusion

Do not treat commercial plan names as if they were the runtime product rights themselves.

### 22.2 Payment-as-right confusion

Do not assume that a successful payment automatically equals clean feature access without entitlement issuance.

### 22.3 Hardcoded feature flags everywhere

Do not scatter feature-access logic across handlers without a unified entitlement model.

### 22.4 Free-user ambiguity

Do not leave free-tier capability undefined.

### 22.5 Entitlement-history loss

Do not lose the history of granted/expired/revoked rights.

### 22.6 Commercial contamination of core domains

Do not bury entitlement logic inside protocols, reminders or labs tables.

---

## 23. Recommended future dependent documents

This document should feed the creation of:

- `docs/82_payment_and_checkout.md`
- `docs/83_paywall_strategy.md`
- `docs/84_commercial_analytics.md`

These names are recommendations and may change.

---

## 24. Final statement

CycleSync should not decide product access through vague premium flags or environment hacks.

It should decide access through a clean entitlement model in which:

- identity is separate from payment;
- payment is separate from rights;
- rights are explicit and queryable;
- plans and keys are just sources of grants;
- feature gates read entitlement truth directly.

That is what will let the product scale commercially without turning access logic into a pile of contradictions.
