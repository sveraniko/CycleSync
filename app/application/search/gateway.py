from typing import Protocol

from app.application.search.schemas import SearchDocument


class SearchGatewayError(RuntimeError):
    pass


class SearchGateway(Protocol):
    async def ensure_index(self) -> None: ...

    async def upsert_documents(self, documents: list[SearchDocument]) -> None: ...

    async def delete_documents(self, document_ids: list[str]) -> None: ...

    async def search(self, query: str, limit: int = 10, offset: int = 0) -> tuple[list[dict], int]: ...

    async def healthcheck(self) -> dict[str, object]: ...
