from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import selectinload

from app.application.search.repository import SearchQueryLogEntry
from app.application.search.schemas import (
    CardMediaItem,
    CardSourceLink,
    CatalogIngredientRow,
    CatalogProjectionRow,
    OpenCard,
)
from app.domain.models import CompoundProduct, SearchProjectionState, SearchQueryLog
from app.domain.models.compound_catalog import ProductMediaRef


class SqlAlchemySearchRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self.session_factory = session_factory

    async def fetch_projection_rows(self, product_ids: list[UUID] | None = None) -> list[CatalogProjectionRow]:
        async with self.session_factory() as session:
            query = (
                select(CompoundProduct)
                .options(
                    selectinload(CompoundProduct.brand),
                    selectinload(CompoundProduct.aliases),
                    selectinload(CompoundProduct.ingredients),
                    selectinload(CompoundProduct.media_refs),
                )
                .where(CompoundProduct.is_active.is_(True))
            )
            if product_ids:
                query = query.where(CompoundProduct.id.in_(product_ids))

            products = (await session.scalars(query)).all()

            rows: list[CatalogProjectionRow] = []
            for product in products:
                rows.append(
                    CatalogProjectionRow(
                        product_id=product.id,
                        product_name=product.display_name,
                        trade_name=product.trade_name,
                        brand_name=product.brand.display_name,
                        release_form=product.release_form,
                        concentration_raw=product.concentration_raw,
                        aliases=[alias.alias_text for alias in product.aliases if alias.is_active],
                        ingredients=[
                            CatalogIngredientRow(
                                ingredient_name=i.ingredient_name,
                                amount=_decimal_str(i.amount),
                                unit=i.unit,
                                qualifier=i.qualifier,
                            )
                            for i in sorted(product.ingredients, key=lambda x: x.sort_order)
                            if i.is_active
                        ],
                        official_url=product.official_url,
                        authenticity_notes=product.authenticity_notes,
                        media_refs=[m.ref_url for m in sorted(product.media_refs, key=lambda x: x.sort_order) if m.is_active],
                    )
                )
            return rows

    async def upsert_projection_state(
        self,
        projection_name: str,
        checkpoint: str,
        checkpointed_at: datetime,
        indexed_documents_count: int,
        rebuild_kind: str,
        last_error: str | None,
    ) -> None:
        async with self.session_factory() as session:
            existing = await session.scalar(
                select(SearchProjectionState).where(SearchProjectionState.projection_name == projection_name)
            )
            if existing is None:
                existing = SearchProjectionState(
                    projection_name=projection_name,
                    checkpoint=checkpoint,
                    checkpointed_at=checkpointed_at,
                    indexed_documents_count=indexed_documents_count,
                    last_rebuild_kind=rebuild_kind,
                    last_error=last_error,
                )
                session.add(existing)
            else:
                existing.checkpoint = checkpoint
                existing.checkpointed_at = checkpointed_at
                existing.indexed_documents_count = indexed_documents_count
                existing.last_rebuild_kind = rebuild_kind
                existing.last_error = last_error
            await session.commit()

    async def log_query(self, entry: SearchQueryLogEntry) -> None:
        async with self.session_factory() as session:
            session.add(
                SearchQueryLog(
                    raw_query=entry.raw_query,
                    normalized_query=entry.normalized_query,
                    source=entry.source,
                    user_id=entry.user_id,
                    result_count=entry.result_count,
                    was_found=entry.was_found,
                )
            )
            await session.commit()

    async def get_open_card(self, product_id: UUID) -> OpenCard | None:
        async with self.session_factory() as session:
            product = await session.scalar(
                select(CompoundProduct)
                .options(
                    selectinload(CompoundProduct.brand),
                    selectinload(CompoundProduct.ingredients),
                    selectinload(CompoundProduct.media_refs),
                    selectinload(CompoundProduct.source_refs),
                )
                .where(CompoundProduct.id == product_id)
            )
            if product is None:
                return None

            components = []
            for i in sorted(product.ingredients, key=lambda x: x.sort_order):
                chunk = i.ingredient_name
                amount = _decimal_str(i.amount)
                if amount and i.unit:
                    chunk = f"{chunk} {amount}{i.unit}"
                components.append(chunk)

            return OpenCard(
                product_id=product.id,
                product_name=product.display_name,
                brand=product.brand.display_name,
                composition_summary="; ".join(components) if components else None,
                form_factor=product.release_form,
                official_url=product.official_url,
                authenticity_notes=product.authenticity_notes,
                media_display_mode=product.media_display_mode,
                media_policy=product.media_policy,
                sync_images=product.sync_images,
                sync_videos=product.sync_videos,
                sync_sources=product.sync_sources,
                source_links=[
                    CardSourceLink(
                        kind=src.source_kind,
                        label=src.label,
                        url=src.url,
                        priority=src.sort_order,
                        source_layer=src.source_layer,
                        is_active=src.is_active,
                    )
                    for src in sorted(product.source_refs, key=lambda x: x.sort_order)
                    if src.is_active
                ],
                media_items=[
                    CardMediaItem(
                        media_kind=media.media_kind,
                        ref=media.ref_url,
                        priority=media.sort_order,
                        is_cover=media.is_cover,
                        source_layer=media.source_layer,
                        is_active=media.is_active,
                    )
                    for media in sorted(product.media_refs, key=lambda x: x.sort_order)
                    if media.is_active
                ],
            )

    async def add_product_media_ref(self, product_id: UUID, ref_url: str, media_kind: str = "external") -> bool:
        async with self.session_factory() as session:
            existing = await session.scalar(
                select(ProductMediaRef).where(
                    ProductMediaRef.product_id == product_id,
                    ProductMediaRef.ref_url == ref_url,
                )
            )
            if existing is not None:
                return False
            max_sort = await session.scalar(
                select(func.max(ProductMediaRef.sort_order)).where(ProductMediaRef.product_id == product_id)
            ) or 0
            session.add(
                ProductMediaRef(
                    product_id=product_id,
                    media_kind=media_kind,
                    ref_url=ref_url,
                    sort_order=max_sort + 1,
                    source_layer="manual",
                )
            )
            await session.commit()
            return True

    async def update_product_media_admin_settings(
        self,
        product_id: UUID,
        *,
        media_policy: str | None = None,
        media_display_mode: str | None = None,
        sync_images: bool | None = None,
        sync_videos: bool | None = None,
        sync_sources: bool | None = None,
    ) -> bool:
        async with self.session_factory() as session:
            product = await session.get(CompoundProduct, product_id)
            if product is None:
                return False
            if media_policy is not None:
                product.media_policy = media_policy
            if media_display_mode is not None:
                product.media_display_mode = media_display_mode
            if sync_images is not None:
                product.sync_images = sync_images
            if sync_videos is not None:
                product.sync_videos = sync_videos
            if sync_sources is not None:
                product.sync_sources = sync_sources
            await session.commit()
            return True


def _decimal_str(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value.normalize(), "f").rstrip("0").rstrip(".") or "0"
