import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.application.protocols.draft_service import DraftApplicationService
from app.application.protocols.schemas import AddProductToDraftResult, DraftItemView, DraftView


@dataclass
class EventRecord:
    event_type: str
    aggregate_type: str
    aggregate_id: UUID
    payload: dict


class FakeDraftRepository:
    def __init__(self) -> None:
        self.user_id = "u1"
        self.draft_id = uuid4()
        self.items: list[DraftItemView] = []
        self.events: list[EventRecord] = []

    async def get_or_create_active_draft(self, user_id: str):
        created = not hasattr(self, "_created")
        self._created = True
        return self._build_draft(user_id), created

    async def get_active_draft(self, user_id: str):
        return self._build_draft(user_id)

    async def add_product_to_draft(self, user_id: str, product_id: UUID) -> AddProductToDraftResult:
        existing = next((i for i in self.items if i.product_id == product_id), None)
        if existing:
            return AddProductToDraftResult(draft=self._build_draft(user_id), item=existing, added=False)

        item = DraftItemView(
            item_id=uuid4(),
            draft_id=self.draft_id,
            product_id=product_id,
            selected_brand="Brand",
            selected_product_name="Product",
            notes=None,
            created_at=datetime.now(timezone.utc),
        )
        self.items.append(item)
        return AddProductToDraftResult(draft=self._build_draft(user_id), item=item, added=True)

    async def remove_item_from_draft(self, user_id: str, item_id: UUID):
        self.items = [i for i in self.items if i.item_id != item_id]
        return self._build_draft(user_id)

    async def clear_draft(self, user_id: str):
        self.items = []
        return self._build_draft(user_id)

    async def get_product_info(self, product_id: UUID):
        return None

    async def enqueue_event(self, *, event_type: str, aggregate_type: str, aggregate_id: UUID, payload: dict, **kwargs):
        self.events.append(
            EventRecord(
                event_type=event_type,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                payload=payload,
            )
        )

    def _build_draft(self, user_id: str) -> DraftView:
        now = datetime.now(timezone.utc)
        return DraftView(
            draft_id=self.draft_id,
            user_id=user_id,
            status="active",
            created_at=now,
            updated_at=now,
            items=list(self.items),
        )


def test_draft_service_create_add_remove_clear_list() -> None:
    repo = FakeDraftRepository()
    service = DraftApplicationService(repository=repo)

    draft = asyncio.run(service.list_draft("u1"))
    assert draft.status == "active"

    product_id = uuid4()
    add_result = asyncio.run(service.add_product_to_draft("u1", product_id))
    assert add_result.added is True
    assert len(add_result.draft.items) == 1

    draft_after_remove = asyncio.run(service.remove_item_from_draft("u1", add_result.item.item_id))
    assert draft_after_remove is not None
    assert len(draft_after_remove.items) == 0

    add_result_2 = asyncio.run(service.add_product_to_draft("u1", product_id))
    assert add_result_2.added is True

    draft_after_clear = asyncio.run(service.clear_draft("u1"))
    assert draft_after_clear is not None
    assert len(draft_after_clear.items) == 0

    event_names = [e.event_type for e in repo.events]
    assert "draft_created" in event_names
    assert "draft_opened" in event_names
    assert "draft_item_added" in event_names
    assert "draft_item_removed" in event_names
    assert "draft_cleared" in event_names


def test_draft_service_add_duplicate_is_idempotent() -> None:
    repo = FakeDraftRepository()
    service = DraftApplicationService(repository=repo)

    product_id = uuid4()
    first = asyncio.run(service.add_product_to_draft("u1", product_id))
    second = asyncio.run(service.add_product_to_draft("u1", product_id))

    assert first.added is True
    assert second.added is False
    assert len(second.draft.items) == 1

    draft_item_added_events = [e for e in repo.events if e.event_type == "draft_item_added"]
    assert len(draft_item_added_events) == 1
