# PR W0 Stabilization Fix Report

## Scope
This PR is stabilization-only for Wave 0 foundation paths. No Wave 1 features, no search logic, no new domain tables, and no business/commercial logic expansion.

## Fixed issues

### 1) Test bootstrap from repo root
- Added `pytest.ini` at repository root.
- Configured `pythonpath = .` and `testpaths = tests` so `pytest -q` resolves `app` imports without manual `PYTHONPATH=.`.

### 2) SQLAlchemy naming convention crash (`KeyError: 'schema_name'`)
- Updated naming convention tokens in `app/domain/db/base.py`.
- Removed unsupported `%(schema_name)s` placeholders.
- Replaced with SQLAlchemy/Alembic-safe placeholders based on table/column/constraint names.

### 3) Alembic migration path cleanup
- Reworked `alembic/env.py` to a **pure sync Alembic online path**.
- Kept async DSN -> sync DSN adaptation (`+asyncpg` -> `+psycopg`).
- Replaced `async_engine_from_config(...)` hybrid flow with `engine_from_config(...)`.
- Online migrations now run through a normal synchronous connection in a single clear path.

## Validation commands
Run from repo root:

```bash
pytest -q
alembic upgrade head
python -m app.main
curl -sSf http://127.0.0.1:8000/health/live
curl -sSf http://127.0.0.1:8000/health/diagnostics
```

For docker compose path (if used in your local/dev flow):

```bash
docker compose up -d --build
docker compose exec app alembic upgrade head
docker compose exec app pytest -q
```

## Non-reproducible-after-fix statements
- `pytest -q` import bootstrap failure for `app` from repo root is fixed.
- SQLAlchemy metadata initialization no longer raises `KeyError: 'schema_name'`.
- Alembic online path is no longer a mixed async/sync hybrid.

## Residual debt / out of scope
- This PR does not add new migration revisions.
- This PR does not introduce Wave 1 logic or any functional expansion.
- Runtime/dependency issues caused by missing local services (Postgres/Redis) remain environment concerns, not scope of this stabilization patch.
