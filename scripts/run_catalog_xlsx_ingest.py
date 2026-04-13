import argparse
import asyncio
from dataclasses import asdict
from pathlib import Path

import structlog

from app.application.catalog.ingest import CatalogIngestService
from app.application.catalog.v2_ingest import CatalogIngestServiceV2
from app.infrastructure.bootstrap import close_infrastructure, init_infrastructure
from app.infrastructure.catalog.repository import SqlAlchemyCatalogRepository
from app.infrastructure.catalog.xlsx_gateway import XlsxCatalogConfig, XlsxCatalogGateway
from app.core.config import get_settings


async def run_catalog_xlsx_ingest(workbook_path: str, sheet_name: str = "Catalog") -> None:
    settings = get_settings()
    logger = structlog.get_logger("cyclesync.catalog_xlsx_ingest")
    workbook = Path(workbook_path)

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
            gateway = XlsxCatalogGateway(XlsxCatalogConfig(workbook_path=str(workbook), sheet_name=sheet_name))
            if sheet_name == "Products":
                service = CatalogIngestServiceV2(
                    source_name="xlsx_file_v2",
                    source_sheet_id=None,
                    source_tab="medical_v2",
                    source_gateway=gateway,
                    repository=repository,
                    workbook_path=str(workbook),
                )
                result = await service.run()
            else:
                service = CatalogIngestService(
                    source_name="xlsx_file",
                    source_sheet_id=None,
                    source_tab=sheet_name,
                    source_gateway=gateway,
                    repository=repository,
                )
                result = await service.run()
            logger.info(
                "catalog_xlsx_ingest_completed",
                workbook_path=str(workbook),
                sheet_name=sheet_name,
                **asdict(result),
            )
    finally:
        await close_infrastructure(infra)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import CycleSync catalog from a local XLSX workbook")
    parser.add_argument("workbook_path", help="Path to the workbook, e.g. docs/medical.xlsx")
    parser.add_argument("--sheet", default="Products", help="Sheet name to import. Use Products for medical_v2 foundation ingest")
    args = parser.parse_args()
    asyncio.run(run_catalog_xlsx_ingest(args.workbook_path, args.sheet))


if __name__ == "__main__":
    main()
