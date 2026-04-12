# PR W7 / PR2 — Specialist response flow MVP

## 1) Response / assignment entities introduced

Updated expert-cases domain with specialist-response truth:

- `expert_cases.specialist_case_responses`
  - `id`
  - `case_id`
  - `responded_by`
  - `response_text`
  - `response_summary` (nullable)
  - `created_at` (base model)
  - `is_final` (default `true`)
- `expert_cases.specialist_cases` extended with:
  - `latest_response_id`
  - `assigned_specialist_id`
  - `answered_at`

The PR intentionally keeps assignment lightweight via `assigned_specialist_id` on case (no heavy staffing subsystem yet).

---

## 2) Real status transitions implemented

Transitions are now explicit in `SpecialistCaseAssemblyService`:

- `awaiting_specialist -> in_review` via `take_case_in_review(...)`
- `in_review -> answered` via `submit_specialist_response(...)`
- `answered -> closed` via `close_case(...)`
- `cancelled` remains independent (not expanded in this PR)

Transition validation is centralized in the application service and not scattered across bot handlers.

---

## 3) How specialist takes case in review

Minimal specialist operator flow is Telegram-native:

1. Open Labs menu -> `Specialist operator`
2. `Awaiting cases`
3. `Open <n>` to inspect case
4. `Take in review`

Service call: `take_case_in_review(case_id, specialist_id)` assigns specialist + moves status to `in_review` + emits lifecycle event.

---

## 4) How specialist response is persisted

Specialist answer is persisted as first-class DB truth:

1. Operator clicks `Submit answer`
2. Bot collects answer text
3. Service calls `submit_specialist_response(...)`
4. Repository inserts row in `specialist_case_responses`
5. Case updated with:
   - `latest_response_id`
   - status `answered`
   - `answered_at`

This avoids ephemeral chat-only storage.

---

## 5) How user sees specialist answer

User flow remains compact:

- `My specialist cases`
- `Open latest case`
- if status is `answered`, latest specialist answer text is displayed

Also case list item now carries latest response summary/time metadata for compact list rendering.

---

## 6) Access / entitlement seam after this PR

Seam is hardened and explicit:

- repository constructor now takes `allow_all_access` (dev mode switch)
- `check_case_access()`:
  - returns `allow_dev_mode` when dev switch is enabled
  - otherwise denies with `missing_expert_case_access_entitlement`

This keeps entitlement enforcement isolated in repository/service seam and removes implicit always-allow behavior.

---

## 7) Events implemented

Added / emitted lifecycle events:

- `specialist_case_taken_in_review`
- `specialist_case_response_created`
- `specialist_case_answered`
- `specialist_case_closed`

Event catalog was updated to include this specialist MVP loop vocabulary.

---

## 8) Exact local verification commands

```bash
pytest -q tests/test_specialist_case_service.py tests/test_bot_labs_smoke.py tests/test_bot_specialist_flow_smoke.py tests/test_db_baseline.py
```

---

## 9) Canonical baseline migration update (in place)

Per baseline-rewrite policy, no new Alembic migration chain was created.

Updated canonical baseline file in place:

- `alembic/versions/20260411_0012_baseline_consolidated.py`
  - extended `expert_cases.specialist_cases` with `answered_at`, `latest_response_id`, `assigned_specialist_id`
  - added new table `expert_cases.specialist_case_responses`
  - added FK `specialist_cases.latest_response_id -> specialist_case_responses.id`

Single canonical baseline is preserved.
