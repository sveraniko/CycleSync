import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.application.protocols.draft_service import DraftApplicationService
from app.application.protocols.pulse_engine import PulseCalculationEngine
from app.application.protocols.schemas import (
    DraftItemView,
    DraftSettingsView,
    DraftView,
    PulseIngredientProfile,
    PulsePlanPreviewView,
    PulseProductProfile,
    StackInputTargetView,
)


class FakePulseRepository:
    def __init__(self) -> None:
        self.draft = self._draft()
        self.events: list[str] = []
        self.last_payload = None
        self.has_previous_preview = False

    async def get_or_create_active_draft(self, user_id: str):
        return self.draft, False

    async def get_draft_settings(self, draft_id):
        return DraftSettingsView(
            draft_id=draft_id,
            protocol_input_mode="total_target",
            weekly_target_total_mg=Decimal("300"),
            duration_weeks=4,
            preset_code="golden_pulse",
            max_injection_volume_ml=Decimal("2.5"),
            max_injections_per_week=3,
            planned_start_date=None,
            updated_at=datetime.now(timezone.utc),
        )

    async def list_pulse_product_profiles(self, draft_id):
        return [
            PulseProductProfile(
                product_id=uuid4(),
                product_name="A",
                concentration_mg_ml=Decimal("250"),
                max_injection_volume_ml=Decimal("2.5"),
                ingredients=[PulseIngredientProfile("a", Decimal("4"), Decimal("250"), True)],
            )
        ]

    async def has_successful_preview_for_draft(self, draft_id):
        return self.has_previous_preview

    async def list_stack_input_targets(self, draft_id, protocol_input_mode=None):
        return []

    async def create_pulse_plan_preview(self, payload):
        self.last_payload = payload
        return PulsePlanPreviewView(
            preview_id=uuid4(),
            draft_id=payload.draft_id,
            protocol_input_mode=payload.protocol_input_mode,
            preset_requested=payload.preset_requested,
            preset_applied=payload.preset_applied,
            status=payload.status,
            degraded_fallback=payload.degraded_fallback,
            summary_metrics=payload.summary_metrics,
            warning_flags=payload.warning_flags,
            allocation_mode=payload.allocation_mode,
            guidance_coverage_score=payload.guidance_coverage_score,
            calculation_quality_flags=payload.calculation_quality_flags,
            entries=payload.entries,
        )

    async def enqueue_event(self, **kwargs):
        self.events.append(kwargs["event_type"])

    @staticmethod
    def _draft() -> DraftView:
        now = datetime.now(timezone.utc)
        draft_id = uuid4()
        return DraftView(
            draft_id=draft_id,
            user_id="u1",
            status="active",
            created_at=now,
            updated_at=now,
            items=[
                DraftItemView(
                    item_id=uuid4(),
                    draft_id=draft_id,
                    product_id=uuid4(),
                    selected_brand="B",
                    selected_product_name="P",
                    notes=None,
                    created_at=now,
                )
            ],
        )


def test_preview_persistence_and_events() -> None:
    repo = FakePulseRepository()
    service = DraftApplicationService(repository=repo, pulse_engine=PulseCalculationEngine())

    preview = asyncio.run(service.generate_pulse_plan_preview("u1"))

    assert preview.status in {"success", "success_with_warnings", "degraded_fallback"}
    assert repo.last_payload is not None
    assert "protocol_calculation_requested" in repo.events
    assert "protocol_calculation_preview_generated" in repo.events


def test_regenerated_event_for_subsequent_preview() -> None:
    repo = FakePulseRepository()
    repo.has_previous_preview = True
    service = DraftApplicationService(repository=repo, pulse_engine=PulseCalculationEngine())

    asyncio.run(service.generate_pulse_plan_preview("u1"))

    assert "protocol_calculation_preview_generated" in repo.events


def test_preview_events_remain_clean_with_optimization_payload() -> None:
    repo = FakePulseRepository()
    service = DraftApplicationService(repository=repo, pulse_engine=PulseCalculationEngine())

    preview = asyncio.run(service.generate_pulse_plan_preview("u1"))

    assert preview.summary_metrics is not None
    assert "optimization_applied" in preview.summary_metrics
    assert "optimization_gain" in preview.summary_metrics
    assert "protocol_calculation_preview_generated" in repo.events
    assert "pulse_plan_preview_failed" not in repo.events


def test_failed_preview_emits_failed_only() -> None:
    class FailingRepo(FakePulseRepository):
        async def get_draft_settings(self, draft_id):
            return None

        async def list_pulse_product_profiles(self, draft_id):
            return []

    repo = FailingRepo()
    service = DraftApplicationService(repository=repo, pulse_engine=PulseCalculationEngine())

    preview = asyncio.run(service.generate_pulse_plan_preview("u1"))

    assert preview.status == "failed_validation"
    assert "pulse_plan_preview_failed" in repo.events
    assert "protocol_calculation_preview_generated" not in repo.events


def test_preview_summary_has_derived_total_weekly_mg_for_stack_smoothing() -> None:
    class StackRepo(FakePulseRepository):
        fixed_product_id = uuid4()

        async def get_draft_settings(self, draft_id):
            settings = await super().get_draft_settings(draft_id)
            settings.protocol_input_mode = "stack_smoothing"
            settings.weekly_target_total_mg = None
            return settings

        async def list_pulse_product_profiles(self, draft_id):
            return [
                PulseProductProfile(
                    product_id=self.fixed_product_id,
                    product_name="A",
                    concentration_mg_ml=Decimal("250"),
                    max_injection_volume_ml=Decimal("2.5"),
                    ingredients=[PulseIngredientProfile("a", Decimal("4"), Decimal("250"), True)],
                )
            ]

        async def list_stack_input_targets(self, draft_id, protocol_input_mode=None):
            return [
                StackInputTargetView(
                    id=uuid4(),
                    draft_id=draft_id,
                    product_id=self.fixed_product_id,
                    protocol_input_mode="stack_smoothing",
                    desired_weekly_mg=Decimal("180"),
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            ]

    repo = StackRepo()
    service = DraftApplicationService(repository=repo, pulse_engine=PulseCalculationEngine())
    preview = asyncio.run(service.generate_pulse_plan_preview("u1"))

    assert preview.summary_metrics is not None
    per_product = preview.summary_metrics.get("per_product_weekly_target_mg") or {}
    assert sum(per_product.values()) == 180.0
