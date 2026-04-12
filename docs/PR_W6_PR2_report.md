# PR W6 / PR2 — AI pre-triage layer for labs

## 1) Introduced triage entities

Added first-class AI pre-triage persistence layer in `ai_triage` schema:

- `ai_triage.lab_triage_runs`
  - `id`
  - `lab_report_id`
  - `user_id`
  - `protocol_id` (nullable)
  - `triage_status`
  - `summary_text`
  - `urgent_flag`
  - `model_name`
  - `prompt_version`
  - `created_at`
  - `completed_at`
  - `raw_result_json` (auxiliary debug/raw snapshot, not the canonical truth)
- `ai_triage.lab_triage_flags`
  - `id`
  - `triage_run_id`
  - `marker_id` (nullable for composite/data-quality flags)
  - `severity` (`info`, `watch`, `warning`, `urgent`)
  - `flag_code`
  - `title`
  - `explanation`
  - `suggested_followup` (nullable)

Canonical structured truth is stored in `lab_triage_flags`; summary text is convenience projection.

---

## 2) AI input contract

Implemented deterministic typed payload (`LabTriageInputPayload`) with:

- report context:
  - `report_id`
  - `user_id`
  - `report_date`
- marker list (`LabTriageInputMarker[]`):
  - `marker_id`
  - `marker_code`
  - `marker_display_name`
  - `category_code`
  - `numeric_value`
  - `unit`
  - `reference_min`
  - `reference_max`
- optional protocol context (`ProtocolTriageContextView`), only when linked protocol is active:
  - `protocol_id`
  - `status`
  - `activated_at`
  - `selected_products`
  - compact `pulse_plan_context`
  - adherence integrity snapshot (`adherence_integrity_state`, `adherence_integrity_detail`)

No OCR and no unstructured media parsing are part of this PR.

---

## 3) Structured output contract

Implemented strict parser (`parse_triage_output`) for model response JSON:

Required:
- `summary: string`
- `urgent_flag: boolean`
- `flags: array`

Flag item contract:
- `marker_code: string | null`
- `severity: info | watch | warning | urgent`
- `flag_code: string`
- `title: string`
- `explanation: string`
- `suggested_followup: string | null`

Optional:
- `recommended_followups: string[]`
- `model_name: string`
- `prompt_version: string`

Invalid schema/types fail safely with parse error handling path (`lab_triage_failed` event + failed run record).

---

## 4) Guardrails

Implemented internal guardrails before/after LLM gateway:

- Empty report => triage blocked.
- Non-numeric marker entry => triage blocked.
- Unsupported unit vs marker accepted units => triage blocked.
- Data completeness warnings injected as structured flags:
  - missing reference ranges (`data.reference_range_missing`)
  - low marker completeness (`data.missing_required_markers`)

Guardrail flags are persisted in same structured flag model.

---

## 5) Bot flow (Telegram-native, minimal)

Added report-level triage actions:

1. User creates/opens active report.
2. User taps `Run AI triage`.
3. Bot shows progress message.
4. Bot returns structured concise result:
   - status
   - urgent indicator
   - summary
   - top flags
5. User can open `Latest triage` later.
6. User can `Regenerate triage` for explicit rerun semantics.

No giant dashboard introduced.

---

## 6) What is intentionally NOT done in this PR

- Specialist case assembly/routing/handoff package generation.
- OCR parsing pipeline for labs.
- Trend dashboard.
- Free-form model prose as canonical truth.

---

## 7) Exact local verification commands

- `pytest -q tests/test_labs_triage_service.py tests/test_bot_labs_smoke.py tests/test_labs_service.py tests/test_db_baseline.py`

---

## 8) Canonical baseline migration update (in place)

Per baseline-rewrite policy, schema changes were made **in the existing canonical baseline migration**:

- updated `alembic/versions/20260411_0012_baseline_consolidated.py` directly;
- added `ai_triage.lab_triage_runs` and `ai_triage.lab_triage_flags` creation there;
- no new alembic revision/migration chain created.
