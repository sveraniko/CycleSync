import asyncio
from uuid import uuid4

from app.application.search.gateway import SearchGatewayError
from app.application.search.repository import SearchQueryLogEntry
from app.application.search.schemas import OpenCard
from app.application.search.service import SearchApplicationService


class FakeRepository:
    def __init__(self) -> None:
        self.logs: list[SearchQueryLogEntry] = []

    async def fetch_projection_rows(self, product_ids=None):
        return []

    async def upsert_projection_state(self, **kwargs):
        return None

    async def log_query(self, entry: SearchQueryLogEntry) -> None:
        self.logs.append(entry)

    async def get_open_card(self, product_id):
        return OpenCard(
            product_id=product_id,
            product_name="Sustanon",
            brand="Brand",
            composition_summary=None,
            form_factor=None,
            official_url=None,
            authenticity_notes=None,
            source_links=[],
            media_items=[],
        )


class FakeGateway:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    async def ensure_index(self):
        return None

    async def upsert_documents(self, documents):
        return None

    async def delete_documents(self, document_ids):
        return None

    async def search(self, query: str, limit: int = 10, offset: int = 0):
        if self.fail:
            raise SearchGatewayError("down")
        pid = str(uuid4())
        return (
            [
                {
                    "id": pid,
                    "product_id": pid,
                    "product_name": "Sustanon 250",
                    "brand": "Pharmacom",
                    "composition_summary": "Testosterone blend",
                    "form_factor": "oil",
                }
            ],
            1,
        )

    async def healthcheck(self):
        return {"ok": not self.fail}


def test_search_service_logs_not_found_on_gateway_failure() -> None:
    repository = FakeRepository()
    service = SearchApplicationService(repository=repository, gateway=FakeGateway(fail=True))

    response = asyncio.run(service.search_products("sustanon", user_id="123"))

    assert response.degraded is True
    assert repository.logs[-1].was_found is False


def test_search_service_returns_hits() -> None:
    repository = FakeRepository()
    service = SearchApplicationService(repository=repository, gateway=FakeGateway())

    response = asyncio.run(service.search_products("sustanon", user_id="123"))

    assert response.total == 1
    assert response.results[0].brand == "Pharmacom"
    assert repository.logs[-1].was_found is True
