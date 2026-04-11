# Migrations policy (pre-release baseline mode)

## Why history was consolidated

CycleSync is still in active pre-release shaping. During this phase, we intentionally avoid preserving every intermediate schema step as permanent migration history. Instead, we keep one canonical baseline that matches the current runtime schema and SQLAlchemy model state.

This keeps bootstrap predictable and prevents wave-by-wave migration chains from becoming long-lived legacy noise.

## Canonical migration

Current canonical baseline:

- `alembic/versions/20260411_0012_baseline_consolidated.py`

This file is the single Alembic `head` and is the only migration required to initialize an empty database.

## Local verification

```bash
alembic upgrade head
pytest -q
```

Optional quick check:

```bash
alembic current
```

Expected: database at `20260411_0012`.

## Ongoing policy

- **Until MVP schema freeze** (see `docs/90_mvp_plan.md`): baseline rewrite is allowed when needed to keep one clean canonical schema.
- **After MVP schema freeze:** stop rewriting baseline; every schema change must be a forward migration with preserved revision history.
- Avoid mixed state: do not keep old wave files alongside a new baseline.
