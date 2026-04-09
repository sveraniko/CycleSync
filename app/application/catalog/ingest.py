from dataclasses import dataclass

from app.application.catalog.mapping import map_sheet_row
from app.application.catalog.repository import CatalogRepository
from app.application.catalog.schemas import IngestIssue, IngestResult


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
        ingest_run_id = await self.repository.start_ingest_run(
            source_name=self.source_name,
            source_sheet_id=self.source_sheet_id,
            source_tab=self.source_tab,
        )

        rows = await self.source_gateway.fetch_rows()
        issues: list[IngestIssue] = []
        created_count = 0
        updated_count = 0
        processed_rows = 0

        for idx, row in enumerate(rows, start=2):
            product, issue = map_sheet_row(row=row, row_number=idx)
            if issue is not None:
                issues.append(issue)
                await self.repository.record_source_row(
                    ingest_run_id=ingest_run_id,
                    row_key=issue.row_key,
                    payload=row,
                    status="invalid",
                    issue_text=issue.message,
                    product_id=None,
                )
                continue

            assert product is not None
            product_id, action = await self.repository.upsert_product(product, ingest_run_id)
            processed_rows += 1
            if action == "created":
                created_count += 1
            else:
                updated_count += 1

            await self.repository.record_source_row(
                ingest_run_id=ingest_run_id,
                row_key=product.source_row_key,
                payload=row,
                status="applied",
                issue_text=None,
                product_id=product_id,
            )

        status = "success" if not issues else "completed_with_issues"
        result = IngestResult(
            status=status,
            total_rows=len(rows),
            processed_rows=processed_rows,
            created_count=created_count,
            updated_count=updated_count,
            issue_count=len(issues),
        )
        await self.repository.finish_ingest_run(ingest_run_id=ingest_run_id, result=result, issues=issues)
        return result
