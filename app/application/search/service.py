from datetime import datetime, timezone
from uuid import UUID

from app.application.search.gateway import SearchGateway, SearchGatewayError
from app.application.search.normalization import normalize_search_query
from app.application.search.projection import CompoundSearchProjectionBuilder
from app.application.search.repository import SearchQueryLogEntry, SearchRepository
from app.application.search.schemas import SearchResponse, SearchResultItem


class SearchApplicationService:
    def __init__(
        self,
        repository: SearchRepository,
        gateway: SearchGateway,
        projection_builder: CompoundSearchProjectionBuilder | None = None,
    ) -> None:
        self.repository = repository
        self.gateway = gateway
        self.projection_builder = projection_builder or CompoundSearchProjectionBuilder()

    async def rebuild_projection(self, product_ids: list[UUID] | None = None) -> int:
        rebuild_kind = "targeted" if product_ids else "full"
        rows = await self.repository.fetch_projection_rows(product_ids=product_ids)
        documents = [self.projection_builder.build_document(row) for row in rows]
        checkpoint = datetime.now(timezone.utc).isoformat()

        try:
            await self.gateway.ensure_index()
            if product_ids:
                await self.gateway.delete_documents([str(pid) for pid in product_ids])
            if documents:
                await self.gateway.upsert_documents(documents)
            await self.repository.upsert_projection_state(
                projection_name="compound_search",
                checkpoint=checkpoint,
                checkpointed_at=datetime.now(timezone.utc),
                indexed_documents_count=len(documents),
                rebuild_kind=rebuild_kind,
                last_error=None,
            )
        except SearchGatewayError as exc:
            await self.repository.upsert_projection_state(
                projection_name="compound_search",
                checkpoint=checkpoint,
                checkpointed_at=datetime.now(timezone.utc),
                indexed_documents_count=0,
                rebuild_kind=rebuild_kind,
                last_error=str(exc),
            )
            raise

        return len(documents)

    async def search_products(
        self,
        query: str,
        user_id: str | None,
        source: str = "text",
        limit: int = 5,
        offset: int = 0,
    ) -> SearchResponse:
        normalized_query = normalize_search_query(query)
        if not normalized_query:
            return SearchResponse(query=query, normalized_query=normalized_query, results=[], total=0)

        try:
            hits, total = await self.gateway.search(normalized_query, limit=limit, offset=offset)
            results = [
                SearchResultItem(
                    document_id=str(hit.get("id")),
                    product_id=UUID(str(hit.get("product_id"))),
                    product_name=str(hit.get("product_name", "")),
                    brand=str(hit.get("brand", "")),
                    composition_summary=hit.get("composition_summary"),
                    form_factor=hit.get("form_factor"),
                )
                for hit in hits
                if hit.get("product_id")
            ]
            await self.repository.log_query(
                SearchQueryLogEntry(
                    raw_query=query,
                    normalized_query=normalized_query,
                    source=source,
                    user_id=user_id,
                    result_count=total,
                    was_found=total > 0,
                )
            )
            return SearchResponse(query=query, normalized_query=normalized_query, results=results, total=total)
        except SearchGatewayError as exc:
            await self.repository.log_query(
                SearchQueryLogEntry(
                    raw_query=query,
                    normalized_query=normalized_query,
                    source=source,
                    user_id=user_id,
                    result_count=0,
                    was_found=False,
                )
            )
            return SearchResponse(
                query=query,
                normalized_query=normalized_query,
                results=[],
                total=0,
                degraded=True,
                degradation_reason=str(exc),
            )

    async def open_card(self, product_id: UUID):
        return await self.repository.get_open_card(product_id)

    async def admin_add_media_ref(self, product_id: UUID, ref_url: str, media_kind: str = "external") -> bool:
        return await self.repository.add_product_media_ref(
            product_id=product_id, ref_url=ref_url, media_kind=media_kind
        )
