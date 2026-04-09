from typing import Protocol
from uuid import UUID

from app.application.catalog.schemas import CatalogProductInput, IngestIssue, IngestResult


class CatalogRepository(Protocol):
    async def start_ingest_run(self, source_name: str, source_sheet_id: str | None, source_tab: str | None) -> UUID: ...

    async def upsert_product(self, product: CatalogProductInput, ingest_run_id: UUID) -> tuple[UUID, str]: ...

    async def record_source_row(
        self,
        ingest_run_id: UUID,
        row_key: str,
        payload: dict[str, str],
        status: str,
        issue_text: str | None,
        product_id: UUID | None,
    ) -> None: ...

    async def finish_ingest_run(self, ingest_run_id: UUID, result: IngestResult, issues: list[IngestIssue]) -> None: ...
