# PR W1 FIX — Stabilization after PR1/PR2/PR3

## Scope
This PR is **stabilization-only** for Wave 1 developer workflow and local infrastructure.
No Wave 2 features were started, and no business-domain logic was expanded.

## What was fixed

1. **Dev dependency install path fixed**
   - `requirements-dev.txt` now pins `black==25.9.0` (existing release).

2. **Script execution path normalized**
   - Canonical execution commands are now package-style:
     - `python -m scripts.run_catalog_ingest`
     - `python -m scripts.rebuild_search_projection`
     - `python -m scripts.check_connectivity`
   - Added `scripts/__init__.py` so `python -m scripts.<module>` works reliably.

3. **`init_infrastructure(...)` signature synchronization**
   - Updated legacy call sites to pass Meilisearch settings:
     - `app/workers/catalog_ingest.py`
     - `scripts/check_connectivity.py`

4. **Local/dev compose now includes Meilisearch**
   - Added `meilisearch` service in `docker-compose.yml`.
   - API and bot services now depend on it (`service_started`).

5. **Environment example completed for W1 search**
   - Added full Meilisearch config block to `.env.example`:
     - `MEILISEARCH_URL`
     - `MEILISEARCH_API_KEY`
     - `MEILISEARCH_INDEX`

6. **Makefile operational targets added**
   - `make catalog-ingest`
   - `make search-rebuild`
   - `make check-connectivity`

## Canonical local commands (Wave 1)

### Install deps
```bash
pip install -r requirements-dev.txt
```

### Start local stack
```bash
docker compose up -d postgres redis meilisearch
```

### Run migrations
```bash
alembic upgrade head
```

### Run maintenance scripts
```bash
python -m scripts.check_connectivity
python -m scripts.run_catalog_ingest
python -m scripts.rebuild_search_projection
```

### Makefile shortcuts
```bash
make check-connectivity
make catalog-ingest
make search-rebuild
```
