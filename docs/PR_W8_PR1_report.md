# PR_W8_PR1 — Entitlement Enforcement Foundation

## 1) Introduced entitlement entities

Implemented first-class access truth in `access` domain:

- `access.entitlements` — entitlement catalog definitions.
- `access.entitlement_grants` — persisted grant/revoke/expiry lifecycle rows.

Catalog includes:
- `bot_access`
- `calculation_access`
- `active_protocol_access`
- `reminders_access`
- `adherence_access`
- `ai_triage_access`
- `expert_case_access`

## 2) Central evaluation

Added `AccessEvaluationService` (`app/application/access/service.py`) as a single runtime policy decision point:

- `evaluate(user_id, entitlement_code)`
  - returns structured `EntitlementDecision`
  - fields: `allowed`, `reason_code`, `grant_source`, `expires_at`, `grant_id`
  - resolves expiration in runtime by converting stale active grants to `expired`
- `grant(...)`
- `revoke(...)`
- `list_user_grants(...)`

No flow-level ad hoc SQL entitlement checks were added; runtime checks route through this service.

## 3) Enforced feature gates in product flows

### AI triage gate
- `LabsTriageService.run_triage` now requires `ai_triage_access`.
- Denied path emits `feature_access_denied` and returns explicit user-facing denial.

### Specialist case gate
- `SpecialistCaseAssemblyService.open_case` now requires `expert_case_access`.
- Replaces previous allow-dev seam in runtime path with entitlement evaluation.
- Denied path emits `feature_access_denied`.

### Reminders gate
- `ReminderApplicationService.update_reminder_settings(reminders_enabled=True)` requires `reminders_access`.
- `materialize_requested_schedules` now suppresses schedule materialization when entitlement is missing.
- `dispatch_due_reminders` now denies send eligibility when entitlement is missing.
- Denied paths emit `feature_access_denied`.

## 4) Minimal manual/admin grant path

Added script: `scripts/manage_entitlements.py`

Supported operations:
- grant entitlement
- revoke entitlement
- list grants (all or active only)

Examples:

```bash
python scripts/manage_entitlements.py grant --user-id tg:100 --entitlement ai_triage_access --source manual
python scripts/manage_entitlements.py revoke --user-id tg:100 --entitlement ai_triage_access --source manual --reason ops_request
python scripts/manage_entitlements.py list --user-id tg:100 --active-only
```

## 5) User-facing denial behavior

Explicit denial responses were wired for key gated flows:

- AI triage: `AI triage requires access.`
- Specialist consultation: `Specialist consultation access is not active.`
- Reminders enablement: `Reminders are disabled because reminder access is missing.`

## 6) Explicitly out of scope in this PR

Not implemented intentionally:
- full payment processor / checkout integration
- giant billing/admin panel
- access keys redemption flow (next PR)
- broad tier matrix beyond selected key feature gates

## 7) Exact local verification commands

```bash
pytest tests/test_access_entitlements.py \
       tests/test_labs_triage_service.py \
       tests/test_specialist_case_service.py \
       tests/test_reminder_materialization.py \
       tests/test_db_baseline.py \
       tests/test_bot_settings_smoke.py
```

## 8) Canonical baseline migration update in place

Per baseline policy, no new Alembic revision chain was created.

Updated in-place file:
- `alembic/versions/20260411_0012_baseline_consolidated.py`

Changes made in canonical baseline:
- added schema: `access`
- added table: `access.entitlements`
- added table: `access.entitlement_grants`
- added required indexes and FK
- seeded entitlement catalog rows
