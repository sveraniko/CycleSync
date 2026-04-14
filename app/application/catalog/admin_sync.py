from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from app.application.catalog.ingest import CatalogIngestService
from app.application.catalog.v2_ingest import CatalogIngestServiceV2, build_v2_inputs, read_workbook_v2
from app.application.search.service import SearchApplicationService
from app.core.config import Settings
from app.infrastructure.bootstrap import close_infrastructure, init_infrastructure
from app.infrastructure.catalog.google_sheets import GoogleSheetsCatalogGateway, GoogleSheetsConfig
from app.infrastructure.catalog.repository import SqlAlchemyCatalogRepository
from app.infrastructure.catalog.xlsx_gateway import XlsxCatalogConfig, XlsxCatalogGateway
from app.infrastructure.search import SqlAlchemySearchRepository


@dataclass(slots=True)
class CatalogAdminRunSummary:
    source_type: str
    mode: str
    status: str
    timestamp: str
    message: str
    counts: dict[str, int] = field(default_factory=dict)


class CatalogAdminSyncService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def get_default_workbook_path(self) -> str:
        return "docs/medical_v2.xlsx"

    def gsheets_is_configured(self) -> tuple[bool, str]:
        if not self._settings.google_sheets_sheet_id.strip():
            return False, "Google Sheets не настроен: отсутствует GOOGLE_SHEETS_SHEET_ID."
        if not self._settings.google_sheets_tab_name.strip():
            return False, "Google Sheets не настроен: отсутствует GOOGLE_SHEETS_TAB_NAME."
        if self._settings.google_sheets_use_service_account:
            has_inline = bool(self._settings.google_sheets_service_account_json.strip())
            has_path = bool(self._settings.google_sheets_credentials_path.strip())
            if not has_inline and not has_path:
                return False, "Google Sheets не настроен: нет credentials для service account."
        return True, "Google Sheets конфигурация выглядит валидной."

    def validate_workbook(self, workbook_path: str | None = None) -> CatalogAdminRunSummary:
        path = Path(workbook_path or self.get_default_workbook_path())
        timestamp = datetime.now(timezone.utc).isoformat()
        if not path.exists():
            return CatalogAdminRunSummary(
                source_type="xlsx",
                mode="validate",
                status="failed",
                timestamp=timestamp,
                message=f"Workbook не найден: {path}",
            )

        try:
            sheets = read_workbook_v2(str(path))
            products, issues = build_v2_inputs(sheets)
            if issues:
                return CatalogAdminRunSummary(
                    source_type="xlsx",
                    mode="validate",
                    status="failed",
                    timestamp=timestamp,
                    message=f"Validation завершилась с ошибками ({len(issues)}).",
                    counts={
                        "rows_total": len(sheets.products),
                        "products_valid": len(products),
                        "errors": len(issues),
                    },
                )
            return CatalogAdminRunSummary(
                source_type="xlsx",
                mode="validate",
                status="success",
                timestamp=timestamp,
                message="Validation прошла успешно.",
                counts={
                    "rows_total": len(sheets.products),
                    "products_valid": len(products),
                    "errors": 0,
                },
            )
        except Exception as exc:
            return CatalogAdminRunSummary(
                source_type="xlsx",
                mode="validate",
                status="failed",
                timestamp=timestamp,
                message=f"Validation не выполнена: {str(exc)[:200]}",
            )

    async def run_xlsx_ingest_apply(self, workbook_path: str | None = None) -> CatalogAdminRunSummary:
        workbook = workbook_path or self.get_default_workbook_path()
        infra = await init_infrastructure(
            postgres_dsn=self._settings.postgres_dsn,
            redis_dsn=self._settings.redis_dsn,
            meilisearch_url=self._settings.meilisearch_url,
            meilisearch_api_key=self._settings.meilisearch_api_key,
            meilisearch_index=self._settings.meilisearch_index,
        )
        try:
            async with infra.db_session_factory() as session:
                repository = SqlAlchemyCatalogRepository(session=session)
                gateway = XlsxCatalogGateway(XlsxCatalogConfig(workbook_path=workbook, sheet_name="Products"))
                service = CatalogIngestServiceV2(
                    source_name="xlsx_file_v2",
                    source_sheet_id=None,
                    source_tab="medical_v2",
                    source_gateway=gateway,
                    repository=repository,
                    workbook_path=workbook,
                )
                result = await service.run()
                return CatalogAdminRunSummary(
                    source_type="xlsx",
                    mode="apply",
                    status=result.status,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    message="XLSX ingest завершён.",
                    counts={
                        "rows_total": result.total_rows,
                        "rows_processed": result.processed_rows,
                        "created": result.created_count,
                        "updated": result.updated_count,
                        "errors": result.issue_count,
                    },
                )
        except Exception as exc:
            return CatalogAdminRunSummary(
                source_type="xlsx",
                mode="apply",
                status="failed",
                timestamp=datetime.now(timezone.utc).isoformat(),
                message=f"Ingest завершился ошибкой: {str(exc)[:200]}",
            )
        finally:
            await close_infrastructure(infra)

    async def run_gsheets_sync_apply(self) -> CatalogAdminRunSummary:
        configured, reason = self.gsheets_is_configured()
        if not configured:
            return CatalogAdminRunSummary(
                source_type="gsheets",
                mode="apply",
                status="failed",
                timestamp=datetime.now(timezone.utc).isoformat(),
                message=reason,
            )
        infra = await init_infrastructure(
            postgres_dsn=self._settings.postgres_dsn,
            redis_dsn=self._settings.redis_dsn,
            meilisearch_url=self._settings.meilisearch_url,
            meilisearch_api_key=self._settings.meilisearch_api_key,
            meilisearch_index=self._settings.meilisearch_index,
        )
        try:
            async with infra.db_session_factory() as session:
                repository = SqlAlchemyCatalogRepository(session=session)
                gateway = GoogleSheetsCatalogGateway(
                    GoogleSheetsConfig(
                        sheet_id=self._settings.google_sheets_sheet_id,
                        tab_name=self._settings.google_sheets_tab_name,
                        credentials_path=self._settings.google_sheets_credentials_path or None,
                        service_account_json=self._settings.google_sheets_service_account_json or None,
                        use_service_account=self._settings.google_sheets_use_service_account,
                    )
                )
                service = CatalogIngestService(
                    source_name="google_sheets",
                    source_sheet_id=self._settings.google_sheets_sheet_id or None,
                    source_tab=self._settings.google_sheets_tab_name or None,
                    source_gateway=gateway,
                    repository=repository,
                )
                result = await service.run()
                return CatalogAdminRunSummary(
                    source_type="gsheets",
                    mode="apply",
                    status=result.status,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    message="Google Sheets sync завершён.",
                    counts={
                        "rows_total": result.total_rows,
                        "rows_processed": result.processed_rows,
                        "created": result.created_count,
                        "updated": result.updated_count,
                        "errors": result.issue_count,
                    },
                )
        except Exception as exc:
            return CatalogAdminRunSummary(
                source_type="gsheets",
                mode="apply",
                status="failed",
                timestamp=datetime.now(timezone.utc).isoformat(),
                message=f"Google Sheets sync завершился ошибкой: {str(exc)[:200]}",
            )
        finally:
            await close_infrastructure(infra)

    async def rebuild_search(self) -> CatalogAdminRunSummary:
        infra = await init_infrastructure(
            postgres_dsn=self._settings.postgres_dsn,
            redis_dsn=self._settings.redis_dsn,
            meilisearch_url=self._settings.meilisearch_url,
            meilisearch_api_key=self._settings.meilisearch_api_key,
            meilisearch_index=self._settings.meilisearch_index,
        )
        try:
            repository = SqlAlchemySearchRepository(infra.db_session_factory)
            service = SearchApplicationService(repository=repository, gateway=infra.search_gateway)
            indexed = await service.rebuild_projection()
            return CatalogAdminRunSummary(
                source_type="search_rebuild",
                mode="apply",
                status="success",
                timestamp=datetime.now(timezone.utc).isoformat(),
                message="Rebuild поиска выполнен.",
                counts={"indexed_documents": indexed},
            )
        except Exception as exc:
            return CatalogAdminRunSummary(
                source_type="search_rebuild",
                mode="apply",
                status="failed",
                timestamp=datetime.now(timezone.utc).isoformat(),
                message=f"Rebuild поиска завершился ошибкой: {str(exc)[:200]}",
            )
        finally:
            await close_infrastructure(infra)

    @staticmethod
    def as_dict(summary: CatalogAdminRunSummary) -> dict[str, object]:
        return asdict(summary)
