import asyncio

import structlog

from app.application.catalog.ingest import CatalogIngestService
from app.core.config import get_settings
from app.infrastructure.bootstrap import close_infrastructure, init_infrastructure
from app.infrastructure.catalog.google_sheets import GoogleSheetsCatalogGateway, GoogleSheetsConfig
from app.infrastructure.catalog.repository import SqlAlchemyCatalogRepository


async def run_catalog_ingest() -> None:
    settings = get_settings()
    logger = structlog.get_logger("cyclesync.catalog_ingest")

    if not settings.catalog_ingest_enabled:
        logger.warning("catalog_ingest_disabled")
        return

    infra = await init_infrastructure(
        postgres_dsn=settings.postgres_dsn,
        redis_dsn=settings.redis_dsn,
        meilisearch_url=settings.meilisearch_url,
        meilisearch_api_key=settings.meilisearch_api_key,
        meilisearch_index=settings.meilisearch_index,
    )
    try:
        async with infra.db_session_factory() as session:
            repository = SqlAlchemyCatalogRepository(session=session)
            gateway = GoogleSheetsCatalogGateway(
                GoogleSheetsConfig(
                    sheet_id=settings.google_sheets_sheet_id,
                    tab_name=settings.google_sheets_tab_name,
                    credentials_path=settings.google_sheets_credentials_path or None,
                    service_account_json=settings.google_sheets_service_account_json or None,
                    use_service_account=settings.google_sheets_use_service_account,
                )
            )
            service = CatalogIngestService(
                source_name="google_sheets",
                source_sheet_id=settings.google_sheets_sheet_id or None,
                source_tab=settings.google_sheets_tab_name or None,
                source_gateway=gateway,
                repository=repository,
            )
            result = await service.run()
            logger.info("catalog_ingest_completed", **result.__dict__)
    finally:
        await close_infrastructure(infra)


if __name__ == "__main__":
    asyncio.run(run_catalog_ingest())
