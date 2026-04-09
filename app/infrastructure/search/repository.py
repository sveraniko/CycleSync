from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import selectinload

from app.application.search.repository import SearchQueryLogEntry
from app.application.search.schemas import CatalogIngredientRow, CatalogProjectionRow, OpenCard
from app.domain.models import CompoundProduct, SearchProjectionState, SearchQueryLog


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
                media_refs=[m.ref_url for m in sorted(product.media_refs, key=lambda x: x.sort_order) if m.is_active],
            )


def _decimal_str(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value.normalize(), "f").rstrip("0").rstrip(".") or "0"
