from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import selectinload

from app.application.protocols.repository import DraftProductInfo
from app.application.protocols.schemas import AddProductToDraftResult, DraftItemView, DraftView
from app.domain.models import Brand, CompoundProduct, OutboxEvent, ProtocolDraft, ProtocolDraftItem


class SqlAlchemyDraftRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self.session_factory = session_factory

    async def get_or_create_active_draft(self, user_id: str) -> tuple[DraftView, bool]:
        async with self.session_factory() as session:
            draft = await self._fetch_active_draft(session, user_id)
            created = False
            if draft is None:
                draft = ProtocolDraft(user_id=user_id, status="active")
                session.add(draft)
                await session.flush()
                created = True
            await session.commit()
            draft = await self._fetch_active_draft(session, user_id)
            if draft is None:  # pragma: no cover
                raise RuntimeError("failed to load active draft after commit")
            return self._to_draft_view(draft), created

    async def get_active_draft(self, user_id: str) -> DraftView | None:
        async with self.session_factory() as session:
            draft = await self._fetch_active_draft(session, user_id)
            return self._to_draft_view(draft) if draft else None

    async def add_product_to_draft(self, user_id: str, product_id: UUID) -> AddProductToDraftResult:
        async with self.session_factory() as session:
            draft = await self._fetch_active_draft(session, user_id)
            if draft is None:
                draft = ProtocolDraft(user_id=user_id, status="active")
                session.add(draft)
                await session.flush()

            product_row = await session.execute(
                select(CompoundProduct.id, CompoundProduct.display_name, Brand.display_name)
                .join(Brand, CompoundProduct.brand_id == Brand.id)
                .where(CompoundProduct.id == product_id, CompoundProduct.is_active.is_(True))
            )
            product = product_row.one_or_none()
            if product is None:
                raise ValueError("product_not_found")

            existing = await session.scalar(
                select(ProtocolDraftItem).where(
                    ProtocolDraftItem.draft_id == draft.id,
                    ProtocolDraftItem.product_id == product_id,
                )
            )
            if existing is None:
                existing = ProtocolDraftItem(
                    draft_id=draft.id,
                    product_id=product_id,
                    selected_product_name=product[1],
                    selected_brand=product[2],
                )
                session.add(existing)
                added = True
            else:
                added = False

            await session.commit()
            draft = await self._fetch_active_draft(session, user_id)
            if draft is None:  # pragma: no cover
                raise RuntimeError("failed to load draft after add")
            item = next((i for i in draft.items if i.product_id == product_id), None)
            if item is None:  # pragma: no cover
                raise RuntimeError("failed to load draft item after add")
            return AddProductToDraftResult(draft=self._to_draft_view(draft), item=self._to_item_view(item), added=added)

    async def remove_item_from_draft(self, user_id: str, item_id: UUID) -> DraftView | None:
        async with self.session_factory() as session:
            draft = await self._fetch_active_draft(session, user_id)
            if draft is None:
                return None
            item = await session.scalar(
                select(ProtocolDraftItem).where(
                    ProtocolDraftItem.id == item_id,
                    ProtocolDraftItem.draft_id == draft.id,
                )
            )
            if item is None:
                return self._to_draft_view(draft)
            await session.delete(item)
            await session.commit()
            draft = await self._fetch_active_draft(session, user_id)
            return self._to_draft_view(draft) if draft else None

    async def clear_draft(self, user_id: str) -> DraftView | None:
        async with self.session_factory() as session:
            draft = await self._fetch_active_draft(session, user_id)
            if draft is None:
                return None
            await session.execute(delete(ProtocolDraftItem).where(ProtocolDraftItem.draft_id == draft.id))
            await session.commit()
            draft = await self._fetch_active_draft(session, user_id)
            return self._to_draft_view(draft) if draft else None

    async def get_product_info(self, product_id: UUID) -> DraftProductInfo | None:
        async with self.session_factory() as session:
            row = await session.execute(
                select(CompoundProduct.id, CompoundProduct.display_name, Brand.display_name)
                .join(Brand, CompoundProduct.brand_id == Brand.id)
                .where(CompoundProduct.id == product_id)
            )
            result = row.one_or_none()
            if result is None:
                return None
            return DraftProductInfo(product_id=result[0], product_name=result[1], brand_name=result[2])

    async def enqueue_event(
        self,
        *,
        event_type: str,
        aggregate_type: str,
        aggregate_id: UUID,
        payload: dict,
        correlation_id: str | None = None,
        occurred_at: datetime | None = None,
    ) -> None:
        async with self.session_factory() as session:
            session.add(
                OutboxEvent(
                    event_type=event_type,
                    aggregate_type=aggregate_type,
                    aggregate_id=aggregate_id,
                    payload_json={
                        **payload,
                        "occurred_at": (occurred_at or datetime.now(timezone.utc)).isoformat(),
                    },
                    correlation_id=correlation_id,
                )
            )
            await session.commit()

    async def _fetch_active_draft(self, session, user_id: str) -> ProtocolDraft | None:
        return await session.scalar(
            select(ProtocolDraft)
            .options(selectinload(ProtocolDraft.items))
            .where(ProtocolDraft.user_id == user_id, ProtocolDraft.status == "active")
        )

    @staticmethod
    def _to_item_view(item: ProtocolDraftItem) -> DraftItemView:
        return DraftItemView(
            item_id=item.id,
            draft_id=item.draft_id,
            product_id=item.product_id,
            selected_brand=item.selected_brand,
            selected_product_name=item.selected_product_name,
            notes=item.notes,
            created_at=item.created_at,
        )

    def _to_draft_view(self, draft: ProtocolDraft) -> DraftView:
        return DraftView(
            draft_id=draft.id,
            user_id=draft.user_id,
            status=draft.status,
            created_at=draft.created_at,
            updated_at=draft.updated_at,
            items=[self._to_item_view(item) for item in draft.items],
        )
