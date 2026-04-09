from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.catalog.normalization import normalize_lookup
from app.application.catalog.schemas import CatalogProductInput, IngestIssue, IngestResult
from app.domain.models import (
    Brand,
    CatalogIngestRun,
    CatalogSourceRecord,
    CompoundAlias,
    CompoundIngredient,
    CompoundProduct,
    ProductMediaRef,
)


class SqlAlchemyCatalogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def start_ingest_run(self, source_name: str, source_sheet_id: str | None, source_tab: str | None) -> UUID:
        run = CatalogIngestRun(
            source_name=source_name,
            source_sheet_id=source_sheet_id,
            source_tab=source_tab,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        self.session.add(run)
        await self.session.flush()
        return run.id

    async def _ensure_brand(self, display_name: str) -> Brand:
        normalized_name = normalize_lookup(display_name)
        query = select(Brand).where(Brand.normalized_name == normalized_name)
        existing = await self.session.scalar(query)
        if existing:
            if existing.display_name != display_name:
                existing.display_name = display_name
            existing.is_active = True
            return existing

        brand = Brand(display_name=display_name, normalized_name=normalized_name, source="google_sheets")
        self.session.add(brand)
        await self.session.flush()
        return brand

    async def upsert_product(self, product: CatalogProductInput, ingest_run_id: UUID) -> tuple[UUID, str]:
        brand = await self._ensure_brand(product.brand_name)
        normalized_trade_name = normalize_lookup(product.trade_name)
        normalized_display_name = normalize_lookup(product.display_name)

        product_query = select(CompoundProduct).where(
            and_(
                CompoundProduct.brand_id == brand.id,
                CompoundProduct.normalized_trade_name == normalized_trade_name,
                CompoundProduct.release_form == product.release_form,
                CompoundProduct.concentration_raw == product.concentration_raw,
            )
        )
        existing = await self.session.scalar(product_query)
        action = "updated"
        if existing is None:
            action = "created"
            existing = CompoundProduct(
                brand_id=brand.id,
                display_name=product.display_name,
                normalized_display_name=normalized_display_name,
                trade_name=product.trade_name,
                normalized_trade_name=normalized_trade_name,
                release_form=product.release_form,
                concentration_raw=product.concentration_raw,
                concentration_value=product.concentration_value,
                concentration_unit=product.concentration_unit,
                concentration_basis=product.concentration_basis,
                official_url=product.official_url,
                authenticity_notes=product.authenticity_notes,
                source="google_sheets",
                source_ref=product.source_row_key,
                is_active=True,
            )
            self.session.add(existing)
            await self.session.flush()
        else:
            existing.display_name = product.display_name
            existing.normalized_display_name = normalized_display_name
            existing.trade_name = product.trade_name
            existing.official_url = product.official_url
            existing.authenticity_notes = product.authenticity_notes
            existing.concentration_value = product.concentration_value
            existing.concentration_unit = product.concentration_unit
            existing.concentration_basis = product.concentration_basis
            existing.is_active = True

        await self._replace_aliases(existing.id, product.aliases)
        await self._replace_ingredients(existing.id, product)
        await self._replace_media(existing.id, "image", product.image_refs)
        await self._replace_media(existing.id, "video", product.video_refs)
        await self.session.flush()
        return existing.id, action

    async def _replace_aliases(self, product_id: UUID, aliases: list[str]) -> None:
        await self.session.execute(delete(CompoundAlias).where(CompoundAlias.product_id == product_id))
        for alias in aliases:
            self.session.add(
                CompoundAlias(
                    product_id=product_id,
                    alias_text=alias,
                    normalized_alias=normalize_lookup(alias),
                    is_active=True,
                )
            )

    async def _replace_ingredients(self, product_id: UUID, product: CatalogProductInput) -> None:
        await self.session.execute(delete(CompoundIngredient).where(CompoundIngredient.product_id == product_id))
        for index, ingredient in enumerate(product.ingredients):
            self.session.add(
                CompoundIngredient(
                    product_id=product_id,
                    ingredient_name=ingredient.ingredient_name,
                    normalized_ingredient_name=normalize_lookup(ingredient.ingredient_name),
                    qualifier=ingredient.qualifier,
                    amount=ingredient.amount,
                    unit=ingredient.unit,
                    basis=ingredient.basis,
                    sort_order=index,
                    is_active=True,
                )
            )

    async def _replace_media(self, product_id: UUID, media_kind: str, refs: list[str]) -> None:
        await self.session.execute(
            delete(ProductMediaRef).where(
                and_(ProductMediaRef.product_id == product_id, ProductMediaRef.media_kind == media_kind)
            )
        )
        for index, ref in enumerate(refs):
            self.session.add(
                ProductMediaRef(
                    product_id=product_id,
                    media_kind=media_kind,
                    ref_url=ref,
                    sort_order=index,
                    is_active=True,
                )
            )

    async def record_source_row(
        self,
        ingest_run_id: UUID,
        row_key: str,
        payload: dict[str, str],
        status: str,
        issue_text: str | None,
        product_id: UUID | None,
    ) -> None:
        fingerprint = sha256(str(sorted(payload.items())).encode("utf-8")).hexdigest()
        record = CatalogSourceRecord(
            ingest_run_id=ingest_run_id,
            source_row_key=row_key,
            payload_json=payload,
            fingerprint=fingerprint,
            status=status,
            issue_text=issue_text,
            product_id=product_id,
        )
        self.session.add(record)

    async def finish_ingest_run(self, ingest_run_id: UUID, result: IngestResult, issues: list[IngestIssue]) -> None:
        run = await self.session.get(CatalogIngestRun, ingest_run_id)
        if run is None:
            raise RuntimeError(f"ingest run {ingest_run_id} was not found")

        run.status = result.status
        run.finished_at = datetime.now(timezone.utc)
        run.total_rows = result.total_rows
        run.processed_rows = result.processed_rows
        run.created_count = result.created_count
        run.updated_count = result.updated_count
        run.issue_count = result.issue_count
        run.details_json = {
            "issues": [{"row_key": issue.row_key, "message": issue.message} for issue in issues[:50]],
        }
        await self.session.commit()
