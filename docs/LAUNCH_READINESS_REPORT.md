# CycleSync — Launch Readiness Report

**Date:** 2026-04-13  
**Audit scope:** Full repository + runtime audit from Wave 0 through W12/PR2  
**Bot token source:** `bot token.txt` in project root  

---

## A. Verdict

### `GO WITH RISKS`

The system is structurally complete for a closed pilot launch. All major product contours are implemented and wired. Architecture discipline is intact. Migration baseline is clean. Operational tooling exists.

The primary blocker (`.env` file missing) has been fixed as part of this audit.

The main **remaining risk** that can sink a pilot is the **empty catalog** — without seeded compounds, search returns nothing and the entire product flow collapses at step 1. This must be resolved before opening the bot to any users.

---

## B. Blockers

### B1. ~~`.env` file did not exist~~ — FIXED

The `.env` file was absent. The bot and API would refuse to start (FastAPI config requires env values, bot raises `RuntimeError` if `BOT_TOKEN` is empty).

**Fix applied:** `.env` created from `.env.example` with bot token pre-filled and all pilot-safe defaults set.

---

### B2. Catalog is empty — MUST RESOLVE BEFORE PILOT

The system is **search-first by design**. If the compound catalog is empty:
- search returns nothing
- `+Draft` is never possible
- pulse engine never has input
- all downstream flows are dead

**Catalog ingest path is Google Sheets only** — there is no xlsx import path in the codebase. The `docs/medical.xlsx` is a validation reference document, not an importable source.

**What must happen before pilot:**
1. Either configure Google Sheets credentials and run `make catalog-ingest`
2. Or manually seed compounds directly into `compound_catalog.*` tables via SQL, then run `make search-rebuild`

Both paths are described in section D below.

---

## C. Risks

### C1. Reminder dispatch is not automated (OPERATIONAL RISK)

The reminder system uses two separate scripts:
- `scripts/materialize_reminders.py` — turns pulse plan lines into reminder events (must run after each protocol activation)
- `scripts/dispatch_reminders.py` — sends due reminders to Telegram (must run on a schedule)

**Neither is auto-executed inside the bot process or the API process.**

If reminders are not dispatched externally (e.g., via cron or periodic Task), users will never receive reminder messages. This silently kills the core product loop.

**For pilot:** Set up a cron job or Windows Task Scheduler to call these scripts every 5–15 minutes.

```
# materialize: run once after each protocol confirm (or periodically)
python -m scripts.materialize_reminders

# dispatch: run every ~5 min
python -m scripts.dispatch_reminders
```

### C2. `EXPERT_CASE_ALLOW_DEV_ACCESS=true` — specialist flow unguarded

The setting `expert_case_allow_dev_access=True` bypasses entitlement check for specialist cases. All users can open specialist cases without paying.

**For closed pilot:** This is acceptable — intentionally open for testing. Document it and revisit before wider launch.

### C3. Commerce mode `disabled` — no live payment flow

`COMMERCE_MODE=disabled` means checkout always returns an error if triggered. Pilot must run purely on access key grants + free tier access.

**For pilot:** Use `scripts/manage_access_keys.py` and `scripts/manage_entitlements.py` to issue access for pilot users.

### C4. Meilisearch has no auth key set

`MEILISEARCH_API_KEY=` is empty. Meilisearch runs without authentication. This is fine for a closed internal pilot on a private network, but insecure if exposed publicly.

**For pilot:** Acceptable. Set a key if exposing to internet.

### C5. AI triage is in `heuristic` mode

`LABS_TRIAGE_GATEWAY_MODE=heuristic` — AI triage runs on rule-based logic without LLM. The product still works; summaries are less narrative. Set `LABS_TRIAGE_GATEWAY_MODE=openai` + `LABS_AI_OPENAI_API_KEY=<key>` to enable GPT-based triage. The gateway uses `httpx` directly (no `openai` SDK dependency required).

### C6. Google Sheets catalog ingest requires service account credentials

To run `make catalog-ingest`, `GOOGLE_SHEETS_USE_SERVICE_ACCOUNT=true` + either `GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON` or `GOOGLE_SHEETS_CREDENTIALS_PATH` must be set. Without these, the ingest worker exits early with `catalog_ingest_disabled` or auth error.

---

## D. Exact Launch Commands

### Step 1 — Bootstrap infrastructure

```bash
# From CycleSync project root
make up
# Starts: PostgreSQL, Redis, Meilisearch, API, Bot
# Wait for healthy checks (postgres: ~10s, redis: ~5s)
```

Or start only infra (not the app containers) for local dev:

```bash
docker compose up -d postgres redis meilisearch
```

### Step 2 — Apply baseline migration

```bash
# Applies the single canonical baseline: 20260411_0012_baseline_consolidated
make db-upgrade

# Verify:
make db-current
# Expected output: 20260411_0012 (head)
```

For local dev (outside Docker), ensure `alembic.ini` `sqlalchemy.url` points to `localhost:5432` (already configured).

### Step 3 — Seed catalog (CRITICAL — do this before any user access)

**Option A — Google Sheets (preferred if credentials available):**
```bash
# In .env:
#   CATALOG_INGEST_ENABLED=true
#   GOOGLE_SHEETS_SHEET_ID=<your sheet id>
#   GOOGLE_SHEETS_USE_SERVICE_ACCOUNT=true
#   GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON=<json string>

make catalog-ingest
```

**Option B — Direct SQL seed (if no Google Sheets):**
Manually INSERT compounds into `compound_catalog.compounds`, `compound_catalog.compound_products`, etc. matching the data model from `alembic/versions/20260411_0012_baseline_consolidated.py`. Then run rebuild (step 4).

### Step 4 — Rebuild search projection

```bash
# Full rebuild of Meilisearch index from DB
make search-rebuild

# Expected output: Full rebuild finished. indexed_documents=<N>
# N should be > 0 if catalog was seeded
```

### Step 5 — Verify connectivity

```bash
python -m scripts.check_connectivity
# Expected: {"postgres": {"ok": true, ...}, "redis": {"ok": true, ...}, "meilisearch": {"ok": true, ...}}
```

### Step 6 — Issue access keys / entitlements for pilot users

```bash
# Create a pilot access key granting full execution access
python -m scripts.manage_access_keys create \
  --key-code PILOT2026 \
  --entitlement bot_access \
  --entitlement calculation_access \
  --entitlement active_protocol_access \
  --entitlement reminders_access \
  --entitlement adherence_access \
  --entitlement ai_triage_access \
  --entitlement expert_case_access \
  --max-redemptions 50 \
  --duration-days 30 \
  --notes "closed pilot wave 1"

# Or grant directly to a specific Telegram user_id:
python -m scripts.manage_entitlements grant \
  --user-id <telegram_user_id> \
  --entitlement reminders_access \
  --source manual
```

### Step 7 — Start reminder automation

Set up recurring execution (every 5–15 minutes):

```bash
# Materialize reminder events from confirmed protocols
python -m scripts.materialize_reminders

# Dispatch due reminders via Telegram
python -m scripts.dispatch_reminders
```

On Windows (Task Scheduler) or Linux (cron):
```bash
# cron entry (every 5 min):
*/5 * * * * cd /path/to/cyclesync && python -m scripts.dispatch_reminders >> /var/log/cyclesync_reminders.log 2>&1
*/5 * * * * cd /path/to/cyclesync && python -m scripts.materialize_reminders >> /var/log/cyclesync_materialize.log 2>&1
```

### Step 8 — Smoke test

```bash
# Unit/integration test suite
pytest -q

# Targeted smoke:
pytest -q tests/test_bot_search_smoke.py tests/test_bot_draft_smoke.py tests/test_pulse_engine.py tests/test_reminder_materialization.py tests/test_access_entitlements.py
```

### Step 9 — Check diagnostics endpoint

```bash
curl http://localhost:8000/health/diagnostics
```

Expected: `readiness.ok=true`, `catalog_source.configured=true` (if Google Sheets set), `commerce.mode=disabled`, `reminders_foundation.materialized_reminder_rows=N`.

---

## E. Pilot Recommended Mode

### Recommended configuration for closed pilot

| Layer | Recommended setting |
|---|---|
| `COMMERCE_MODE` | `disabled` — issue access via keys/manual grants |
| `EXPERT_CASE_ALLOW_DEV_ACCESS` | `true` — allow all pilot users to test specialist flow |
| `LABS_TRIAGE_GATEWAY_MODE` | `heuristic` — works without LLM key; upgrade to `openai` when ready |
| `CATALOG_INGEST_ENABLED` | `true` if Google Sheets credentials available |
| `MEILISEARCH_API_KEY` | can be empty for private network pilot |
| Reminder dispatch | manual cron / Task Scheduler, every 5–15 min |
| Bot access | access key redemption flow (PILOT2026 or similar) |

### What NOT to enable at pilot launch

- `COMMERCE_MODE=live` — no live payment provider configured or tested
- `LABS_TRIAGE_GATEWAY_MODE=openai` — only if OpenAI API key is confirmed working
- Public Meilisearch port exposure — lock it to internal network

### What to keep under manual control

- Entitlement grants (monitor via `scripts/manage_entitlements.py list`)
- Specialist case routing (no specialist routing automation exists yet — all cases are manually handled)
- Reminder dispatch cron health (if cron stops, reminders stop silently)

---

## F. Minimal Operator Runbook

### Morning before opening to users

1. **Check infra health:**
   ```
   curl http://localhost:8000/health/ready
   ```
   — Both `postgres.ok` and `redis.ok` must be `true`. Meilisearch degraded is acceptable (fallback exists).

2. **Check diagnostics:**
   ```
   curl http://localhost:8000/health/diagnostics
   ```
   — Look at: `reminders_foundation.failed_delivery_count`, `operational_reliability.dead_letter_count`, `operational_reliability.outbox_dead_letter_count`.

3. **Check reminder dispatch cron is running** (any pending reminders dispatched).

4. **If catalog changed:** run `make catalog-ingest` + `make search-rebuild`.

### After start — first 30 minutes

1. Watch logs: `make logs`
2. Confirm bot responds to `/start` command
3. Try a search query via Telegram
4. Confirm results return and `+Draft` button works

### What to check in diagnostics during pilot

| Metric | What it means if elevated |
|---|---|
| `reminders_foundation.failed_delivery_count` | Telegram delivery failures — check bot token or Telegram API |
| `reminders_foundation.broken_protocol_count` | Protocols marked broken from missed reminders — expected/normal |
| `operational_reliability.dead_letter_count` | Background job failures — inspect `ops.job_runs` table |
| `operational_reliability.outbox_dead_letter_count` | Outbox event failures — run `python -m scripts.ops_retry_dead_letter_jobs` |
| `commerce.failed_checkouts` | Checkout errors — should be 0 in `disabled` mode |

### How to fix typical pilot fail cases

**Reminders stopped firing:**
```bash
python -m scripts.materialize_reminders
python -m scripts.dispatch_reminders
```

**Dead-letter outbox events:**
```bash
python -m scripts.ops_retry_dead_letter_jobs 100
```

**Outbox replay:**
```bash
python -m scripts.ops_replay_outbox 50
```

**Search returning nothing:**
```bash
make search-rebuild
```

**User can't access feature (entitlement denied):**
```bash
python -m scripts.manage_entitlements list --user-id <telegram_user_id>
python -m scripts.manage_entitlements grant --user-id <id> --entitlement reminders_access
```

**View user access key redemptions:**
```bash
python -m scripts.manage_access_keys inspect --key-code PILOT2026
python -m scripts.manage_access_keys list-redemptions --key-code PILOT2026
```

**Inspect operational state:**
```bash
python -m scripts.ops_inspect
```

**Full infra reset (dev only — destroys all data):**
```bash
make down
make db-reset-local
make search-rebuild
```

---

## G. Code Fixes Applied in This Audit

### Fix 1 — Created `.env` file

**File:** `.env` (created from `.env.example`)

**Why needed:** The file did not exist. Without it:
- `pydantic-settings` reads from environment only (no defaults for `BOT_TOKEN`)
- Bot raises `RuntimeError("BOT_TOKEN is required to run bot shell")`
- Docker Compose `env_file: - .env` silently fails

**What was filled in:**
- `BOT_TOKEN` from `bot token.txt`
- All DSN/URL values pointing to Docker Compose service names (correct for `make up` flow)
- Safe pilot defaults: `COMMERCE_MODE=disabled`, `LABS_TRIAGE_GATEWAY_MODE=heuristic`, `EXPERT_CASE_ALLOW_DEV_ACCESS=true`

---

## H. Product Flow Coverage Audit

### What was verified by code inspection

| Flow | Status | Notes |
|---|---|---|
| search → open → +draft | ✅ Implemented | Full flow in `SearchApplicationService` + bot handlers |
| input mode: `auto_pulse` | ✅ Implemented | `PulseCalculationEngine` handles all 4 modes |
| input mode: `total_target` | ✅ Implemented | Strongest implemented mode per docs |
| input mode: `stack_smoothing` | ✅ Implemented | Per W11/W12 PRs |
| input mode: `inventory_constrained` | ✅ Implemented | Gated behind `inventory_constrained_access` entitlement |
| pulse plan preview generation | ✅ Implemented | `estimate_from_preview` path exists |
| active protocol start | ✅ Implemented | Two-step start with pre-start estimate |
| course estimator | ✅ Implemented | W12/PR1+PR2 complete |
| reminder materialization | ✅ Implemented | `materialize_reminders.py` + worker |
| reminder dispatch | ✅ Implemented | `dispatch_reminders.py` w/ Telegram delivery |
| adherence write (done/snooze/skip) | ✅ Implemented | `AdherenceApplicationService` |
| protocol broken-state detection | ✅ Implemented | `adherence.protocol_adherence_summaries` with `integrity_state` |
| labs manual entry | ✅ Implemented | `LabsApplicationService` + wizard bot flow |
| AI triage run | ✅ Implemented | `LabsTriageService`, heuristic mode available without key |
| specialist case open → response | ✅ Implemented | `SpecialistCaseAssemblyService` |
| access key redemption | ✅ Implemented | `AccessKeyService` |
| checkout (free/gift path) | ✅ Implemented | `FreePaymentProvider` available |
| checkout (live provider) | ⚠️ NOT LAUNCH-READY | `COMMERCE_MODE=disabled`; live providers exist as stubs only |

### What could NOT be verified without live infra

- Actual Meilisearch search quality on real catalog data
- Reminder Telegram delivery latency
- Protocol broken-state threshold tuning in real usage
- AI triage quality in heuristic vs OpenAI mode
- Specialist routing behavior (no automated specialist assignment exists)

---

## I. Migration Discipline Status

**CLEAN.**

- Single canonical baseline: `alembic/versions/20260411_0012_baseline_consolidated.py`
- `down_revision = None` — confirmed
- No stale migration files in `alembic/versions/`
- Baseline was last updated in-place at W11/PR3 for `inventory_constrained` schema additions
- W12/PR1+PR2 required no schema changes — baseline unchanged
- `alembic upgrade head` applies this single file from scratch on empty DB

**Post-MVP freeze policy (from docs):** After MVP launch, in-place baseline rewrites stop. Every schema change must be a proper forward migration. Do not break this discipline.
