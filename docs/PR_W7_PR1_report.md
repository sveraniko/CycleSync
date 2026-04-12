# PR W7 / PR1 — Specialist case assembly foundation

## 1) Introduced case entities
Added first-class specialist case entities in `expert_cases` schema:
- `expert_cases.specialist_cases`
- `expert_cases.specialist_case_snapshots`

Lifecycle object is `specialist_cases`; immutable context package is `specialist_case_snapshots` with `(case_id, snapshot_version)` uniqueness.

## 2) Snapshot payload structure
Snapshot payload is assembled from structured system truth and includes:
- `user_id`
- `protocol` summary/settings
- `pulse_plan` summary
- `adherence` integrity + counts
- `lab_report` metadata + entries
- `triage` latest triage summary + flags
- `user_note`
- `assembled_at`, `assembly_version`

The payload is deterministic and repeatable, not free-form chat prose.

## 3) User flow: Consult specialist
Implemented minimal bot flow:
1. User opens report/triage actions.
2. Taps `Consult specialist`.
3. Optionally enters short note/question.
4. System assembles context snapshot.
5. Case + snapshot persisted.
6. User gets confirmation with case ID/status/snapshot version.

Also added minimal read path:
- list own specialist cases,
- open latest case summary/status.

## 4) Status model
Supported explicit statuses:
- `opened`
- `assembled`
- `awaiting_specialist`
- `in_review`
- `answered`
- `closed`
- `cancelled`

Current flow initializes to `opened`, then moves to `awaiting_specialist` after snapshot assembly.

## 5) Access/commercial seam
Access check is isolated in repository seam `check_case_access()` returning `SpecialistCaseAccessDecision`.
Current baseline is allow-all with explicit TODO for entitlement enforcement (`expert_case_access`) in next PR.
Paywall logic is intentionally not embedded in bot handlers.

## 6) Intentionally NOT done in this PR
- No specialist inbox/chat platform.
- No operator CRM/admin panel.
- No specialist routing/assignment.
- No payment processor implementation.
- No full reply workflow/state-machine overreach.

## 7) Exact local verification commands
- `pytest tests/test_specialist_case_service.py`
- `pytest tests/test_bot_labs_smoke.py`
- `pytest tests/test_db_baseline.py`

## 8) Canonical baseline migration updated in place
Per baseline policy, no new Alembic revision was created.
Schema changes for specialist cases were added directly into:
- `alembic/versions/20260411_0012_baseline_consolidated.py`

The file now creates both specialist case tables and related indexes/FK in-place as part of the single canonical baseline.
