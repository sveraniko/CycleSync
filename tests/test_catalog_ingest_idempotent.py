from dataclasses import dataclass
from uuid import UUID, uuid4

from app.application.catalog.ingest import CatalogIngestService
from app.application.catalog.schemas import CatalogProductInput, IngestIssue, IngestResult


class FakeGateway:
    def __init__(self, rows: list[dict[str, str]]) -> None:
        self.rows = rows

    async def fetch_rows(self) -> list[dict[str, str]]:
        return self.rows


@dataclass
class FakeRepo:
    ingest_runs: list[UUID]
    rows: dict[str, CatalogProductInput]
    last_result: IngestResult | None = None

    async def start_ingest_run(self, source_name: str, source_sheet_id: str | None, source_tab: str | None) -> UUID:
        run_id = uuid4()
        self.ingest_runs.append(run_id)
        return run_id

    async def upsert_product(self, product: CatalogProductInput, ingest_run_id: UUID) -> tuple[UUID, str]:
        existing = self.rows.get(product.source_row_key)
        if existing is None:
            self.rows[product.source_row_key] = product
            return uuid4(), "created"
        self.rows[product.source_row_key] = product
        return uuid4(), "updated"

    async def record_source_row(
        self,
        ingest_run_id: UUID,
        row_key: str,
        payload: dict[str, str],
        status: str,
        issue_text: str | None,
        product_id: UUID | None,
    ) -> None:
        return None

    async def finish_ingest_run(self, ingest_run_id: UUID, result: IngestResult, issues: list[IngestIssue]) -> None:
        self.last_result = result


def test_ingest_is_idempotent_for_same_payload() -> None:
    import asyncio

    async def _run() -> None:
        rows = [
            {
                "row_key": "1",
                "brand": "BrandA",
                "display_name": "Product A",
                "trade_name": "Product A",
                "aliases": "prod a",
            }
        ]
        repo = FakeRepo(ingest_runs=[], rows={})

        service = CatalogIngestService(
            source_name="google_sheets",
            source_sheet_id="sheet-1",
            source_tab="Catalog",
            source_gateway=FakeGateway(rows),
            repository=repo,
        )

        first = await service.run()
        second = await service.run()

        assert first.created_count == 1
        assert second.created_count == 0
        assert second.updated_count == 1
        assert second.issue_count == 0

    asyncio.run(_run())
