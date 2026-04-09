import asyncio

from app.workers.catalog_ingest import run_catalog_ingest


if __name__ == "__main__":
    asyncio.run(run_catalog_ingest())
