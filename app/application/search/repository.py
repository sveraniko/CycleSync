from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.application.search.schemas import CatalogProjectionRow, OpenCard


@dataclass(slots=True)
class SearchQueryLogEntry:
    raw_query: str
    normalized_query: str
    source: str
    user_id: str | None
    result_count: int
    was_found: bool


class SearchRepository(Protocol):
    async def fetch_projection_rows(self, product_ids: list[UUID] | None = None) -> list[CatalogProjectionRow]: ...

    async def upsert_projection_state(
        self,
        projection_name: str,
        checkpoint: str,
        checkpointed_at: datetime,
        indexed_documents_count: int,
        rebuild_kind: str,
        last_error: str | None,
    ) -> None: ...

    async def log_query(self, entry: SearchQueryLogEntry) -> None: ...

    async def get_open_card(self, product_id: UUID) -> OpenCard | None: ...
