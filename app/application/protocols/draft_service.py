from datetime import datetime, timezone
from uuid import UUID

from app.application.protocols.repository import DraftRepository
from app.application.protocols.schemas import AddProductToDraftResult, DraftView


class DraftApplicationService:
    def __init__(self, repository: DraftRepository) -> None:
        self.repository = repository

    async def get_or_create_active_draft(self, user_id: str) -> DraftView:
        draft, created = await self.repository.get_or_create_active_draft(user_id)
        if created:
            await self.repository.enqueue_event(
                event_type="draft_created",
                aggregate_type="protocol_draft",
                aggregate_id=draft.draft_id,
                payload={"user_id": user_id},
            )
        return draft

    async def list_draft(self, user_id: str) -> DraftView:
        draft = await self.get_or_create_active_draft(user_id)
        await self.repository.enqueue_event(
            event_type="draft_opened",
            aggregate_type="protocol_draft",
            aggregate_id=draft.draft_id,
            payload={"user_id": user_id, "item_count": len(draft.items)},
        )
        return draft

    async def add_product_to_draft(self, user_id: str, product_id: UUID) -> AddProductToDraftResult:
        result = await self.repository.add_product_to_draft(user_id=user_id, product_id=product_id)
        if result.added:
            await self.repository.enqueue_event(
                event_type="draft_item_added",
                aggregate_type="protocol_draft",
                aggregate_id=result.draft.draft_id,
                payload={
                    "user_id": user_id,
                    "item_id": str(result.item.item_id),
                    "product_id": str(product_id),
                },
            )
        return result

    async def remove_item_from_draft(self, user_id: str, item_id: UUID) -> DraftView | None:
        draft = await self.repository.remove_item_from_draft(user_id=user_id, item_id=item_id)
        if draft is None:
            return None
        await self.repository.enqueue_event(
            event_type="draft_item_removed",
            aggregate_type="protocol_draft",
            aggregate_id=draft.draft_id,
            payload={"user_id": user_id, "item_id": str(item_id)},
        )
        return draft

    async def clear_draft(self, user_id: str) -> DraftView | None:
        draft = await self.repository.clear_draft(user_id=user_id)
        if draft is None:
            return None
        await self.repository.enqueue_event(
            event_type="draft_cleared",
            aggregate_type="protocol_draft",
            aggregate_id=draft.draft_id,
            payload={"user_id": user_id},
        )
        return draft

    async def mark_ready_for_calculation(self, user_id: str) -> DraftView:
        draft = await self.get_or_create_active_draft(user_id)
        await self.repository.enqueue_event(
            event_type="draft_ready_for_calculation",
            aggregate_type="protocol_draft",
            aggregate_id=draft.draft_id,
            payload={
                "user_id": user_id,
                "item_count": len(draft.items),
                "occurred_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return draft
