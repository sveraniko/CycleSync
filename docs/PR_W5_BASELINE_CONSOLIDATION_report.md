# PR W5: Baseline Consolidation Report

## 1) Why migration chain was consolidated

CycleSync is in pre-release active development. The previous Alembic history represented multiple wave-by-wave intermediate states. To keep migration discipline aligned with current product stage, the chain was collapsed into one canonical baseline reflecting current schema reality, not historical iteration artifacts.

## 2) Canonical baseline file

- `alembic/versions/20260411_0012_baseline_consolidated.py`
- Alembic `down_revision = None`
- Alembic `head = 20260411_0012`

## 3) Replaced/removed migration files

Removed and replaced by the consolidated baseline:

1. `alembic/versions/20260409_0001_baseline_schemas_and_ops.py`
2. `alembic/versions/20260409_0002_compound_catalog_foundation.py`
3. `alembic/versions/20260409_0003_search_foundation.py`
4. `alembic/versions/20260409_0004_protocol_draft_foundation.py`
5. `alembic/versions/20260409_0005_wave2_pr1_pulse_prep_foundation.py`
6. `alembic/versions/20260409_0006_wave2_pr2_pulse_engine_preview.py`
7. `alembic/versions/20260409_0007_wave2_pr3_protocol_activation_foundation.py`
8. `alembic/versions/20260410_0008_wave3_pr1_pulse_allocation_core.py`
9. `alembic/versions/20260411_0009_wave4_pr1_reminder_materialization_foundation.py`
10. `alembic/versions/20260411_0010_wave4_pr2_reminder_runtime_execution.py`
11. `alembic/versions/20260411_0011_wave5_pr1_adherence_intelligence.py`

## 4) How to verify locally

```bash
alembic upgrade head
alembic current
pytest -q
```

Optional reset flow:

```bash
make db-reset-local
```

## 5) Forward policy

- Pre-MVP freeze: baseline rewrite is allowed when schema undergoes substantial restructuring.
- Post-MVP freeze: baseline rewrite stops; true migration history must be preserved for every schema change.
- Mixed mode is forbidden: no parallel coexistence of old wave chain and a new baseline.

## 6) Scope covered by baseline

Consolidated baseline includes the current schema state for:

- compound catalog foundation;
- search projection/query foundation;
- protocol drafts/settings + active protocol lifecycle foundations;
- pulse preview / active protocol planning foundations;
- reminders runtime and execution tables;
- adherence event truth + summary layer;
- ops/outbox/projection checkpoint foundations;
- required indexes and constraints used by runtime behavior.
