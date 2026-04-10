import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.application.protocols.draft_service import DraftApplicationService
from app.application.protocols.pulse_engine import PulseCalculationEngine
from app.application.protocols.schemas import (
    ActiveProtocolView,
    DraftItemView,
    DraftSettingsView,
    DraftView,
    PulseIngredientProfile,
    PulsePlanPreviewView,
    PulseProductProfile,
)


class FakeActivationRepository:
    def __init__(self) -> None:
        self.draft = self._draft()
        self.events: list[str] = []
        self.preview_payloads = []
        self.promoted = ActiveProtocolView(
            protocol_id=uuid4(),
            draft_id=self.draft.draft_id,
            source_preview_id=uuid4(),
            pulse_plan_id=uuid4(),
            status="active",
            settings_snapshot={"preset_code": "layered_pulse", "duration_weeks": 8, "weekly_target_total_mg": "250"},
            summary_metrics={"flatness_stability_score": 82.3},
            warning_flags=[],
        )

    async def get_or_create_active_draft(self, user_id: str):
        return self.draft, False

    async def get_draft_settings(self, draft_id):
        return DraftSettingsView(
            draft_id=draft_id,
            weekly_target_total_mg=Decimal("250"),
            duration_weeks=8,
            preset_code="layered_pulse",
            max_injection_volume_ml=Decimal("2.0"),
            max_injections_per_week=3,
            planned_start_date=None,
            updated_at=datetime.now(timezone.utc),
        )

    async def list_pulse_product_profiles(self, draft_id):
        return [
            PulseProductProfile(
                product_id=uuid4(),
                product_name="P",
                concentration_mg_ml=Decimal("250"),
                max_injection_volume_ml=Decimal("2.5"),
                ingredients=[PulseIngredientProfile("ing", Decimal("4"), Decimal("250"), True)],
            )
        ]

    async def has_successful_preview_for_draft(self, draft_id):
        return False

    async def create_pulse_plan_preview(self, payload):
        self.preview_payloads.append(payload)
        return PulsePlanPreviewView(
            preview_id=uuid4(),
            draft_id=payload.draft_id,
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

    async def promote_latest_preview_to_active(self, user_id: str) -> ActiveProtocolView:
        return self.promoted

    async def enqueue_event(self, **kwargs):
        self.events.append(kwargs["event_type"])

    @staticmethod
    def _draft() -> DraftView:
        now = datetime.now(timezone.utc)
        draft_id = uuid4()
        return DraftView(
            draft_id=draft_id,
            user_id="u1",
            status="draft",
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


def test_preview_then_activation_events_flow() -> None:
    repo = FakeActivationRepository()
    service = DraftApplicationService(repository=repo, pulse_engine=PulseCalculationEngine())

    asyncio.run(service.generate_pulse_plan_preview("u1"))
    active = asyncio.run(service.confirm_latest_preview_activation("u1"))

    assert active.status == "active"
    assert repo.preview_payloads
    assert "pulse_plan_preview_generated" in repo.events
    assert "protocol_activated" in repo.events
    assert "pulse_plan_activated" in repo.events
    assert "reminder_schedule_requested" in repo.events
