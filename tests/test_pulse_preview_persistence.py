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
)


class FakePulseRepository:
    def __init__(self) -> None:
        self.draft = self._draft()
        self.events: list[str] = []
        self.last_payload = None

    async def get_or_create_active_draft(self, user_id: str):
        return self.draft, False

    async def get_draft_settings(self, draft_id):
        return DraftSettingsView(
            draft_id=draft_id,
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

    async def create_pulse_plan_preview(self, payload):
        self.last_payload = payload
        return PulsePlanPreviewView(
            preview_id=uuid4(),
            draft_id=payload.draft_id,
            preset_requested=payload.preset_requested,
            preset_applied=payload.preset_applied,
            status=payload.status,
            degraded_fallback=payload.degraded_fallback,
            summary_metrics=payload.summary_metrics,
            warning_flags=payload.warning_flags,
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
    assert "pulse_calculation_started" in repo.events
    assert "pulse_plan_preview_generated" in repo.events

