# PR W6 / PR3 — provider-backed AI triage gateway

## 1) Added provider-backed gateway
- Added `OpenAILabsTriageGateway` in `app/infrastructure/labs/openai_triage_gateway.py`.
- Gateway uses provider config from settings (`labs_ai_*`), sends structured prompt input, enforces timeout via `httpx.AsyncClient`, and normalizes provider output into strict app-level dict contract.
- Vendor raw response is not persisted in app layer as canonical payload; gateway extracts only structured JSON result.

## 2) Gateway modes implemented
Runtime mode selection added via `GatewayModeLabsTriageGateway`:
- `heuristic`
- `provider`
- `provider_with_heuristic_fallback`

Configured by `settings.labs_triage_gateway_mode` and wired in `build_labs_triage_gateway(settings)`.

## 3) Provider prompt/input strategy
- Added dedicated versioned prompt builder `LabsTriagePromptBuilder` (`app/infrastructure/labs/provider_triage_prompt.py`).
- Includes:
  - structured marker payload,
  - reference ranges,
  - protocol context,
  - adherence integrity snapshot when available,
  - explicit JSON-only output contract,
  - explicit constraints (no unsupported claims, no treatment prescription, no free-form prose).
- Prompt version is explicit (`labs_ai_prompt_version`) and injected into contract.

## 4) Structured output discipline
- Existing strict parser path in `parse_triage_output` is preserved.
- Provider output is parsed in gateway as JSON object; malformed payload raises `LabsTriageGatewayError`.
- `LabsTriageService` handles `LabsTriageGatewayError` as a safe failure path with failed triage run + `lab_triage_failed` event.

## 5) Fallback policy
- `provider_with_heuristic_fallback` mode attempts provider first; on provider error it logs fallback reason and runs heuristic gateway.
- `provider` mode is strict: if provider is unconfigured/unavailable, triage fails explicitly (no silent fake success).
- `heuristic` mode preserves baseline operation.

## 6) Guardrails preserved
Pre-provider and post-provider guardrails remain in service:
- empty report blocked,
- unsupported units blocked,
- numeric-only marker values required,
- low completeness warning,
- missing reference ranges warning,
- strict severity/field validation for output flags.

## 7) Diagnostics/observability
- `/health/diagnostics` now includes `labs_triage` block:
  - active mode,
  - provider,
  - provider configured flag,
  - resolved model,
  - prompt version.
- Bot startup logs configured gateway diagnostics.
- Provider gateway tracks `last_provider_failure_category` in diagnostics payload.

## 8) Exact local verification commands
- `pytest tests/test_labs_triage_provider_gateway.py`
- `pytest tests/test_labs_triage_service.py`
- `pytest tests/test_health.py`

## 9) Canonical baseline migration policy
- No schema changes were required for this PR.
- Therefore canonical baseline migration `alembic/versions/20260411_0012_baseline_consolidated.py` was intentionally left unchanged.
- Policy preserved: no new migration chain created.
