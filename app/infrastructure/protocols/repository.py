from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import selectinload

from app.application.protocols.repository import DraftCalculationProductInfo, DraftProductInfo
from app.application.protocols.schemas import (
    AddProductToDraftResult,
    DraftItemView,
    DraftSettingsInput,
    DraftSettingsView,
    DraftView,
    PulseIngredientProfile,
    PulsePlanEntry,
    PulsePlanPreviewPersistPayload,
    PulsePlanPreviewView,
    PulseProductProfile,
)
from app.domain.models import (
    Brand,
    CompoundIngredient,
    CompoundProduct,
    OutboxEvent,
    ProtocolDraft,
    ProtocolDraftItem,
    ProtocolDraftSettings,
    PulseCalculationRun,
    PulsePlanPreview,
    PulsePlanPreviewEntry,
)


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
            settings = await self._get_settings(session, draft.id)
            return self._to_draft_view(draft, settings), created

    async def get_active_draft(self, user_id: str) -> DraftView | None:
        async with self.session_factory() as session:
            draft = await self._fetch_active_draft(session, user_id)
            if draft is None:
                return None
            settings = await self._get_settings(session, draft.id)
            return self._to_draft_view(draft, settings)

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
            settings = await self._get_settings(session, draft.id)
            return AddProductToDraftResult(
                draft=self._to_draft_view(draft, settings),
                item=self._to_item_view(item),
                added=added,
            )

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
                settings = await self._get_settings(session, draft.id)
                return self._to_draft_view(draft, settings)
            await session.delete(item)
            await session.commit()
            draft = await self._fetch_active_draft(session, user_id)
            if draft is None:
                return None
            settings = await self._get_settings(session, draft.id)
            return self._to_draft_view(draft, settings)

    async def clear_draft(self, user_id: str) -> DraftView | None:
        async with self.session_factory() as session:
            draft = await self._fetch_active_draft(session, user_id)
            if draft is None:
                return None
            await session.execute(delete(ProtocolDraftItem).where(ProtocolDraftItem.draft_id == draft.id))
            await session.commit()
            draft = await self._fetch_active_draft(session, user_id)
            if draft is None:
                return None
            settings = await self._get_settings(session, draft.id)
            return self._to_draft_view(draft, settings)

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

    async def upsert_draft_settings(self, draft_id: UUID, settings: DraftSettingsInput) -> DraftSettingsView:
        async with self.session_factory() as session:
            existing = await self._get_settings(session, draft_id)
            if existing is None:
                row = ProtocolDraftSettings(draft_id=draft_id)
                session.add(row)
                await session.flush()
            else:
                row = await session.scalar(select(ProtocolDraftSettings).where(ProtocolDraftSettings.draft_id == draft_id))
                if row is None:  # pragma: no cover
                    raise RuntimeError("failed to resolve settings row")

            row.weekly_target_total_mg = settings.weekly_target_total_mg
            row.duration_weeks = settings.duration_weeks
            row.preset_code = settings.preset_code
            row.max_injection_volume_ml = settings.max_injection_volume_ml
            row.max_injections_per_week = settings.max_injections_per_week
            row.planned_start_date = settings.planned_start_date
            await session.commit()
            await session.refresh(row)
            return self._to_settings_view(row)

    async def get_draft_settings(self, draft_id: UUID) -> DraftSettingsView | None:
        async with self.session_factory() as session:
            row = await self._get_settings(session, draft_id)
            return self._to_settings_view(row) if row else None

    async def list_calculation_products(self, draft_id: UUID) -> list[DraftCalculationProductInfo]:
        async with self.session_factory() as session:
            rows = await session.execute(
                select(
                    CompoundProduct.id,
                    CompoundProduct.display_name,
                    CompoundProduct.is_automatable,
                    CompoundProduct.max_injection_volume_ml,
                    CompoundIngredient.ingredient_name,
                    CompoundIngredient.half_life_days,
                )
                .join(ProtocolDraftItem, ProtocolDraftItem.product_id == CompoundProduct.id)
                .outerjoin(CompoundIngredient, CompoundIngredient.product_id == CompoundProduct.id)
                .where(ProtocolDraftItem.draft_id == draft_id)
                .order_by(CompoundProduct.display_name, CompoundIngredient.sort_order)
            )
            grouped: dict[UUID, DraftCalculationProductInfo] = {}
            for product_id, display_name, is_automatable, max_volume, ingredient_name, half_life in rows:
                if product_id not in grouped:
                    grouped[product_id] = DraftCalculationProductInfo(
                        product_id=product_id,
                        product_name=display_name,
                        is_automatable=is_automatable,
                        max_injection_volume_ml=max_volume,
                        ingredient_names=[],
                        has_half_life=False,
                    )
                if ingredient_name:
                    grouped[product_id].ingredient_names.append(ingredient_name)
                if half_life is not None:
                    grouped[product_id].has_half_life = True
            return list(grouped.values())

    async def list_pulse_product_profiles(self, draft_id: UUID) -> list[PulseProductProfile]:
        async with self.session_factory() as session:
            rows = await session.execute(
                select(
                    CompoundProduct.id,
                    CompoundProduct.display_name,
                    CompoundProduct.concentration_value,
                    CompoundProduct.max_injection_volume_ml,
                    CompoundIngredient.ingredient_name,
                    CompoundIngredient.half_life_days,
                    CompoundIngredient.amount,
                    CompoundIngredient.is_pulse_driver,
                )
                .join(ProtocolDraftItem, ProtocolDraftItem.product_id == CompoundProduct.id)
                .outerjoin(CompoundIngredient, CompoundIngredient.product_id == CompoundProduct.id)
                .where(ProtocolDraftItem.draft_id == draft_id)
                .order_by(CompoundProduct.display_name, CompoundIngredient.sort_order)
            )
            grouped: dict[UUID, PulseProductProfile] = {}
            for row in rows:
                if row[0] not in grouped:
                    grouped[row[0]] = PulseProductProfile(
                        product_id=row[0],
                        product_name=row[1],
                        concentration_mg_ml=row[2],
                        max_injection_volume_ml=row[3],
                        ingredients=[],
                    )
                if row[4]:
                    grouped[row[0]].ingredients.append(
                        PulseIngredientProfile(
                            ingredient_name=row[4],
                            half_life_days=row[5],
                            amount_mg=row[6],
                            is_pulse_driver=row[7],
                        )
                    )
            return list(grouped.values())

    async def create_pulse_plan_preview(self, payload: PulsePlanPreviewPersistPayload) -> PulsePlanPreviewView:
        async with self.session_factory() as session:
            run = PulseCalculationRun(
                draft_id=payload.draft_id,
                preset_requested=payload.preset_requested,
                preset_applied=payload.preset_applied,
                status=payload.status,
                degraded_fallback=payload.degraded_fallback,
                settings_snapshot_json=payload.settings_snapshot,
                summary_metrics_json=payload.summary_metrics,
                warning_flags_json=payload.warning_flags,
                error_message=payload.error_message,
            )
            session.add(run)
            await session.flush()

            preview = PulsePlanPreview(
                draft_id=payload.draft_id,
                calculation_run_id=run.id,
                preset_requested=payload.preset_requested,
                preset_applied=payload.preset_applied,
                status=payload.status,
                degraded_fallback=payload.degraded_fallback,
                settings_snapshot_json=payload.settings_snapshot,
                summary_metrics_json=payload.summary_metrics,
                warning_flags_json=payload.warning_flags,
            )
            session.add(preview)
            await session.flush()

            for entry in payload.entries:
                session.add(
                    PulsePlanPreviewEntry(
                        preview_id=preview.id,
                        day_offset=entry.day_offset,
                        scheduled_day=entry.scheduled_day,
                        product_id=entry.product_id,
                        ingredient_context=entry.ingredient_context,
                        volume_ml=entry.volume_ml,
                        computed_mg=entry.computed_mg,
                        injection_event_key=entry.injection_event_key,
                        sequence_no=entry.sequence_no,
                    )
                )
            await session.commit()

            return PulsePlanPreviewView(
                preview_id=preview.id,
                draft_id=payload.draft_id,
                preset_requested=payload.preset_requested,
                preset_applied=payload.preset_applied,
                status=payload.status,
                degraded_fallback=payload.degraded_fallback,
                summary_metrics=payload.summary_metrics,
                warning_flags=payload.warning_flags,
                entries=payload.entries,
            )

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

    async def _get_settings(self, session, draft_id: UUID) -> ProtocolDraftSettings | None:
        return await session.scalar(select(ProtocolDraftSettings).where(ProtocolDraftSettings.draft_id == draft_id))

    @staticmethod
    def _to_settings_view(row: ProtocolDraftSettings) -> DraftSettingsView:
        return DraftSettingsView(
            draft_id=row.draft_id,
            weekly_target_total_mg=row.weekly_target_total_mg,
            duration_weeks=row.duration_weeks,
            preset_code=row.preset_code,
            max_injection_volume_ml=row.max_injection_volume_ml,
            max_injections_per_week=row.max_injections_per_week,
            planned_start_date=row.planned_start_date,
            updated_at=row.updated_at,
        )

    def _to_draft_view(self, draft: ProtocolDraft, settings: ProtocolDraftSettings | None) -> DraftView:
        return DraftView(
            draft_id=draft.id,
            user_id=draft.user_id,
            status=draft.status,
            created_at=draft.created_at,
            updated_at=draft.updated_at,
            items=[self._to_item_view(item) for item in draft.items],
            settings=self._to_settings_view(settings) if settings else None,
        )
