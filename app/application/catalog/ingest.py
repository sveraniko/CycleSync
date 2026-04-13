from dataclasses import dataclass

from app.application.catalog.mapping import map_sheet_row
from app.application.catalog.repository import CatalogRepository
from app.application.catalog.schemas import CatalogProductInput, IngestIssue, IngestResult


class CatalogSourceGateway:
    async def fetch_rows(self) -> list[dict[str, str]]:
        raise NotImplementedError


@dataclass(slots=True)
class CatalogIngestService:
    source_name: str
    source_sheet_id: str | None
    source_tab: str | None
    source_gateway: CatalogSourceGateway
    repository: CatalogRepository

    async def run(self) -> IngestResult:
        rows = await self.source_gateway.fetch_rows()
        products: list[CatalogProductInput] = []
        issues: list[IngestIssue] = []
        for idx, row in enumerate(rows, start=2):
            product, issue = map_sheet_row(row=row, row_number=idx)
            if issue is not None:
                issues.append(issue)
                continue
            assert product is not None
            products.append(product)
        return await self.run_from_products(products, issues=issues, raw_rows=rows)

    async def run_from_products(
        self,
        products: list[CatalogProductInput],
        *,
        issues: list[IngestIssue] | None = None,
        raw_rows: list[dict[str, str]] | None = None,
    ) -> IngestResult:
        ingest_run_id = await self.repository.start_ingest_run(
            source_name=self.source_name,
            source_sheet_id=self.source_sheet_id,
            source_tab=self.source_tab,
        )
        known_issues = list(issues or [])
        created_count = 0
        updated_count = 0
        processed_rows = 0

        for issue in known_issues:
            await self.repository.record_source_row(
                ingest_run_id=ingest_run_id,
                row_key=issue.row_key,
                payload={},
                status="invalid",
                issue_text=issue.message,
                product_id=None,
            )

        for product in products:
            product_id, action = await self.repository.upsert_product(product, ingest_run_id)
            processed_rows += 1
            if action == "created":
                created_count += 1
            else:
                updated_count += 1
            await self.repository.record_source_row(
                ingest_run_id=ingest_run_id,
                row_key=product.source_row_key,
                payload=product.source_payload,
                status="applied",
                issue_text=None,
                product_id=product_id,
            )

        status = "success" if not known_issues else "completed_with_issues"
        total_rows = len(raw_rows) if raw_rows is not None else len(products) + len(known_issues)
        result = IngestResult(
            status=status,
            total_rows=total_rows,
            processed_rows=processed_rows,
            created_count=created_count,
            updated_count=updated_count,
            issue_count=len(known_issues),
        )
        await self.repository.finish_ingest_run(ingest_run_id=ingest_run_id, result=result, issues=known_issues)
        return result
