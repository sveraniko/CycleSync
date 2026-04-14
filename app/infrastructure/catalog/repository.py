from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.catalog.normalization import normalize_lookup
from app.application.catalog.schemas import (
    CatalogProductInput,
    IngestIssue,
    IngestResult,
    MediaInput,
    SourceLinkInput,
)
from app.domain.models import (
    Brand,
    CatalogIngestRun,
    CatalogSourceRecord,
    CompoundAlias,
    CompoundIngredient,
    CompoundProduct,
    ProductMediaRef,
    ProductSourceRef,
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
                product_key=product.product_key,
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
                max_injection_volume_ml=product.max_injection_volume_ml,
                is_automatable=product.is_automatable,
                pharmacology_notes=product.pharmacology_notes,
                composition_basis_notes=product.composition_basis_notes,
                package_kind=product.package_kind,
                volume_per_package_ml=product.volume_per_package_ml,
                unit_strength_mg=product.unit_strength_mg,
                units_per_package=product.units_per_package,
                source="google_sheets",
                source_ref=product.source_row_key,
                is_active=True,
            )
            self.session.add(existing)
            await self.session.flush()
        else:
            existing.product_key = product.product_key or existing.product_key
            existing.display_name = product.display_name
            existing.normalized_display_name = normalized_display_name
            existing.trade_name = product.trade_name
            if existing.sync_sources:
                existing.official_url = product.official_url
            existing.authenticity_notes = product.authenticity_notes
            existing.max_injection_volume_ml = product.max_injection_volume_ml
            existing.is_automatable = product.is_automatable
            existing.pharmacology_notes = product.pharmacology_notes
            existing.composition_basis_notes = product.composition_basis_notes
            existing.concentration_value = product.concentration_value
            existing.concentration_unit = product.concentration_unit
            existing.concentration_basis = product.concentration_basis
            # Update packaging metadata only when the source provides values
            if product.package_kind is not None:
                existing.package_kind = product.package_kind
            if product.volume_per_package_ml is not None:
                existing.volume_per_package_ml = product.volume_per_package_ml
            if product.unit_strength_mg is not None:
                existing.unit_strength_mg = product.unit_strength_mg
            if product.units_per_package is not None:
                existing.units_per_package = product.units_per_package
            existing.is_active = True

        await self._replace_aliases(existing.id, product.aliases)
        await self._replace_ingredients(existing.id, product)
        if product.media_items:
            await self._sync_import_media_items(
                existing.id,
                product.media_items,
                sync_images=existing.sync_images,
                sync_videos=existing.sync_videos,
            )
        else:
            if existing.sync_images:
                await self._replace_import_media(existing.id, "image", product.image_refs)
            if existing.sync_videos:
                await self._replace_import_media(existing.id, "video", product.video_refs)
        await self._sync_import_source_links(existing.id, product.source_links, sync_sources=existing.sync_sources)
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
                    parent_substance=ingredient.parent_substance,
                    ingredient_name=ingredient.ingredient_name,
                    normalized_ingredient_name=normalize_lookup(ingredient.ingredient_name),
                    ester_name=ingredient.ester_name,
                    qualifier=ingredient.qualifier,
                    amount=ingredient.amount,
                    unit=ingredient.unit,
                    basis=ingredient.basis,
                    amount_per_ml_mg=ingredient.amount_per_ml_mg,
                    amount_per_unit_mg=ingredient.amount_per_unit_mg,
                    half_life_days=ingredient.half_life_days,
                    active_fraction=ingredient.active_fraction,
                    tmax_hours=ingredient.tmax_hours,
                    release_model=ingredient.release_model,
                    pk_notes=ingredient.pk_notes,
                    dose_guidance_min_mg_week=ingredient.dose_guidance_min_mg_week,
                    dose_guidance_max_mg_week=ingredient.dose_guidance_max_mg_week,
                    dose_guidance_typical_mg_week=ingredient.dose_guidance_typical_mg_week,
                    is_pulse_driver=ingredient.is_pulse_driver,
                    sort_order=index,
                    is_active=True,
                )
            )

    async def _replace_import_media(self, product_id: UUID, media_kind: str, refs: list[str]) -> None:
        await self.session.execute(
            delete(ProductMediaRef).where(
                and_(
                    ProductMediaRef.product_id == product_id,
                    ProductMediaRef.media_kind == media_kind,
                    ProductMediaRef.source_layer == "import",
                )
            )
        )
        for index, ref in enumerate(refs):
            self.session.add(
                ProductMediaRef(
                    product_id=product_id,
                    media_kind=media_kind,
                    ref_url=ref,
                    sort_order=index,
                    source_layer="import",
                    is_active=True,
                )
            )

    async def _sync_import_media_items(
        self,
        product_id: UUID,
        media_items: list[MediaInput],
        *,
        sync_images: bool,
        sync_videos: bool,
    ) -> None:
        import_items = [item for item in media_items if (item.source_layer or "import") == "import"]
        image_items = [item for item in import_items if item.media_kind == "image"]
        video_items = [item for item in import_items if item.media_kind in {"video", "gif", "animation"}]

        if sync_images:
            await self.session.execute(
                delete(ProductMediaRef).where(
                    and_(
                        ProductMediaRef.product_id == product_id,
                        ProductMediaRef.media_kind == "image",
                        ProductMediaRef.source_layer == "import",
                    )
                )
            )
            for item in sorted(image_items, key=lambda x: x.priority):
                self.session.add(
                    ProductMediaRef(
                        product_id=product_id,
                        media_kind=item.media_kind,
                        ref_url=item.ref,
                        sort_order=item.priority,
                        is_cover=item.is_cover,
                        source_layer="import",
                        is_active=item.is_active,
                    )
                )

        if sync_videos:
            await self.session.execute(
                delete(ProductMediaRef).where(
                    and_(
                        ProductMediaRef.product_id == product_id,
                        ProductMediaRef.media_kind.in_(["video", "gif", "animation"]),
                        ProductMediaRef.source_layer == "import",
                    )
                )
            )
            for item in sorted(video_items, key=lambda x: x.priority):
                self.session.add(
                    ProductMediaRef(
                        product_id=product_id,
                        media_kind=item.media_kind,
                        ref_url=item.ref,
                        sort_order=item.priority,
                        is_cover=item.is_cover,
                        source_layer="import",
                        is_active=item.is_active,
                    )
                )

    async def _sync_import_source_links(self, product_id: UUID, source_links: list[SourceLinkInput], *, sync_sources: bool) -> None:
        if not sync_sources:
            return
        await self.session.execute(
            delete(ProductSourceRef).where(
                and_(ProductSourceRef.product_id == product_id, ProductSourceRef.source_layer == "import")
            )
        )
        for item in sorted(source_links, key=lambda x: x.priority):
            if (item.source_layer or "import") != "import":
                continue
            self.session.add(
                ProductSourceRef(
                    product_id=product_id,
                    source_kind=item.kind,
                    label=item.label,
                    url=item.url,
                    sort_order=item.priority,
                    source_layer="import",
                    is_active=item.is_active,
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
