# PR_W8_PR2 — Access Key Activation Flow

## 1) Introduced access-key entities

Added canonical access-key entities in `access` domain:

- `access.access_keys`
- `access.access_key_entitlements`
- `access.access_key_redemptions`

Key lifecycle fields include status (`active`, `disabled`, `exhausted`, `expired`), redemption counters, expiration, creator source, notes, and auditable redemption result metadata.

## 2) Redemption flow

Introduced `AccessKeyService` as a central application service for:

- create key
- redeem key
- disable key
- inspect key
- list key redemptions

Redemption path is explicit and auditable:

1. load key by code
2. validate lifecycle state (exists, active, not expired, not exhausted)
3. enforce duplicate policy
4. map key entitlements to grants deterministically
5. write redemption audit row with result
6. emit events (`access_key_redeemed` or `access_key_redemption_failed`)

## 3) Explicit duplicate/multi-use policy

Policy selected and enforced:

- **duplicate redemption by same user:** forbidden (`access_key_already_redeemed_by_user`)
- **multi-user redemption:** allowed while `redeemed_count < max_redemptions`
- key transitions to `exhausted` at limit

## 4) How key redemption creates entitlement grants

On success, key templates (`access_key_entitlements`) are converted into real `access.entitlement_grants` rows through `AccessEvaluationService.grant(...)`:

- `user_id` from redeemer
- `entitlement_code` from key mapping
- `granted_by_source = access_key`
- `source_ref = key_code`
- `expires_at` from `grant_duration_days` if configured

This preserves entitlement model as runtime truth and keeps `entitlement_granted` event emission on the standard grant path.

## 5) User-facing activation flow (Telegram)

Added minimal bot flow in `app/bots/handlers/access_keys.py`:

- trigger messages: `Activate` / `Redeem key` / `Активировать`
- bot asks for key
- key is validated and redeemed
- user receives explicit success/failure response
- success output includes entitlement list + expiration

## 6) Manual/admin operator path

Added script `scripts/manage_access_keys.py`:

- `create` key with one or more `--entitlement`
- optional `--max-redemptions`
- optional `--expires-at`
- optional `--duration-days`
- `disable` key
- `inspect` key
- `list-redemptions`

## 7) Events added

- `access_key_created`
- `access_key_redeemed`
- `access_key_redemption_failed`
- `access_key_disabled`

`entitlement_granted` continues to be produced by standard grant path.

## 8) Exact local verification commands

```bash
pytest tests/test_access_keys.py \
       tests/test_bot_access_key_smoke.py \
       tests/test_access_entitlements.py \
       tests/test_db_baseline.py
```

## 9) Canonical baseline migration updated in place

Per baseline policy, no new Alembic migration chain was created.

Updated existing canonical baseline in place:

- `alembic/versions/20260411_0012_baseline_consolidated.py`

Changes in that file:

- added `access.access_keys`
- added `access.access_key_entitlements`
- added `access.access_key_redemptions`
- added FK/index constraints for deterministic key lifecycle + audit reads
