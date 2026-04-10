from datetime import datetime, timezone
from uuid import UUID

from app.application.protocols.pulse_engine import PulseCalculationEngine
from app.application.protocols.repository import DraftRepository
from app.application.protocols.schemas import (
    ActiveProtocolView,
    AddProductToDraftResult,
    DraftReadinessResult,
    DraftSettingsInput,
    DraftSettingsView,
    DraftView,
    PulsePlanPreviewPersistPayload,
    PulsePlanPreviewView,
)


class DraftReadinessValidator:
    async def validate(self, draft: DraftView) -> DraftReadinessResult:
        raise NotImplementedError


class DraftApplicationService:
    def __init__(
        self,
        repository: DraftRepository,
        readiness_validator: DraftReadinessValidator | None = None,
        pulse_engine: PulseCalculationEngine | None = None,
    ) -> None:
        self.repository = repository
        self.readiness_validator = readiness_validator
        self.pulse_engine = pulse_engine

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

    async def save_draft_settings(self, user_id: str, settings: DraftSettingsInput) -> DraftSettingsView:
        draft = await self.get_or_create_active_draft(user_id)
        saved = await self.repository.upsert_draft_settings(draft_id=draft.draft_id, settings=settings)
        await self.repository.enqueue_event(
            event_type="draft_settings_updated",
            aggregate_type="protocol_draft",
            aggregate_id=draft.draft_id,
            payload={
                "user_id": user_id,
                "preset_code": saved.preset_code,
                "duration_weeks": saved.duration_weeks,
            },
        )
        return saved

    async def get_draft_settings(self, user_id: str) -> DraftSettingsView | None:
        draft = await self.get_or_create_active_draft(user_id)
        return await self.repository.get_draft_settings(draft_id=draft.draft_id)

    async def get_draft_readiness(self, user_id: str) -> DraftReadinessResult:
        if self.readiness_validator is None:
            raise RuntimeError("readiness validator is not configured")
        draft = await self.get_or_create_active_draft(user_id)
        return await self.readiness_validator.validate(draft)

    async def generate_pulse_plan_preview(self, user_id: str) -> PulsePlanPreviewView:
        if self.pulse_engine is None:
            raise RuntimeError("pulse engine is not configured")

        draft = await self.get_or_create_active_draft(user_id)
        settings = await self.repository.get_draft_settings(draft.draft_id)
        products = await self.repository.list_pulse_product_profiles(draft.draft_id)

        await self.repository.enqueue_event(
            event_type="pulse_calculation_started",
            aggregate_type="protocol_draft",
            aggregate_id=draft.draft_id,
            payload={"user_id": user_id},
        )

        result = self.pulse_engine.calculate(settings=settings, products=products)
        had_previous_preview = await self.repository.has_successful_preview_for_draft(draft.draft_id)
        payload = PulsePlanPreviewPersistPayload(
            draft_id=draft.draft_id,
            preset_requested=result.preset_requested,
            preset_applied=result.preset_applied,
            status=result.status,
            degraded_fallback=result.degraded_fallback,
            settings_snapshot={
                "weekly_target_total_mg": str(settings.weekly_target_total_mg) if settings else None,
                "duration_weeks": settings.duration_weeks if settings else None,
                "preset_code": settings.preset_code if settings else None,
                "max_injection_volume_ml": str(settings.max_injection_volume_ml) if settings else None,
                "max_injections_per_week": settings.max_injections_per_week if settings else None,
                "planned_start_date": settings.planned_start_date.isoformat() if settings and settings.planned_start_date else None,
            },
            summary_metrics=result.summary_metrics,
            warning_flags=result.warning_flags,
            allocation_mode=result.allocation_mode,
            guidance_coverage_score=result.guidance_coverage_score,
            calculation_quality_flags=result.calculation_quality_flags,
            allocation_details=result.allocation_details,
            entries=result.entries,
            error_message=result.error_message,
        )
        preview = await self.repository.create_pulse_plan_preview(payload)

        if preview.status == "failed_validation":
            await self.repository.enqueue_event(
                event_type="pulse_plan_preview_failed",
                aggregate_type="pulse_plan_preview",
                aggregate_id=preview.preview_id,
                payload={
                    "user_id": user_id,
                    "draft_id": str(draft.draft_id),
                    "validation_issues": result.validation_issues,
                },
            )
        else:
            preview_event_type = "pulse_plan_preview_regenerated" if had_previous_preview else "pulse_plan_preview_generated"
            await self.repository.enqueue_event(
                event_type=preview_event_type,
                aggregate_type="pulse_plan_preview",
                aggregate_id=preview.preview_id,
                payload={"user_id": user_id, "draft_id": str(draft.draft_id), "status": preview.status},
            )

        return preview

    async def confirm_latest_preview_activation(self, user_id: str) -> ActiveProtocolView:
        active = await self.repository.promote_latest_preview_to_active(user_id=user_id)
        await self.repository.enqueue_event(
            event_type="protocol_activated",
            aggregate_type="protocol",
            aggregate_id=active.protocol_id,
            payload={
                "user_id": user_id,
                "draft_id": str(active.draft_id),
                "source_preview_id": str(active.source_preview_id) if active.source_preview_id else None,
            },
        )
        await self.repository.enqueue_event(
            event_type="pulse_plan_activated",
            aggregate_type="pulse_plan",
            aggregate_id=active.pulse_plan_id,
            payload={"user_id": user_id, "protocol_id": str(active.protocol_id)},
        )
        await self.repository.enqueue_event(
            event_type="reminder_schedule_requested",
            aggregate_type="protocol",
            aggregate_id=active.protocol_id,
            payload={"user_id": user_id, "pulse_plan_id": str(active.pulse_plan_id)},
        )
        return active

    async def cancel_active_protocol(self, user_id: str) -> bool:
        protocol_id = await self.repository.cancel_active_protocol(user_id=user_id)
        if protocol_id is None:
            return False
        await self.repository.enqueue_event(
            event_type="protocol_cancelled",
            aggregate_type="protocol",
            aggregate_id=protocol_id,
            payload={"user_id": user_id},
        )
        return True
