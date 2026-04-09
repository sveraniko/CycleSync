from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.application.protocols.schemas import (
    AddProductToDraftResult,
    DraftSettingsInput,
    DraftSettingsView,
    DraftView,
    PulsePlanPreviewPersistPayload,
    PulsePlanPreviewView,
    PulseProductProfile,
)


@dataclass(slots=True)
class DraftProductInfo:
    product_id: UUID
    product_name: str
    brand_name: str


@dataclass(slots=True)
class DraftCalculationProductInfo:
    product_id: UUID
    product_name: str
    is_automatable: bool
    max_injection_volume_ml: Decimal | None
    ingredient_names: list[str]
    has_half_life: bool


class DraftRepository:
    async def get_or_create_active_draft(self, user_id: str) -> tuple[DraftView, bool]:
        raise NotImplementedError

    async def get_active_draft(self, user_id: str) -> DraftView | None:
        raise NotImplementedError

    async def add_product_to_draft(self, user_id: str, product_id: UUID) -> AddProductToDraftResult:
        raise NotImplementedError

    async def remove_item_from_draft(self, user_id: str, item_id: UUID) -> DraftView | None:
        raise NotImplementedError

    async def clear_draft(self, user_id: str) -> DraftView | None:
        raise NotImplementedError

    async def get_product_info(self, product_id: UUID) -> DraftProductInfo | None:
        raise NotImplementedError

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
        raise NotImplementedError

    async def upsert_draft_settings(self, draft_id: UUID, settings: DraftSettingsInput) -> DraftSettingsView:
        raise NotImplementedError

    async def get_draft_settings(self, draft_id: UUID) -> DraftSettingsView | None:
        raise NotImplementedError

    async def list_calculation_products(self, draft_id: UUID) -> list[DraftCalculationProductInfo]:
        raise NotImplementedError

    async def list_pulse_product_profiles(self, draft_id: UUID) -> list[PulseProductProfile]:
        raise NotImplementedError

    async def create_pulse_plan_preview(self, payload: PulsePlanPreviewPersistPayload) -> PulsePlanPreviewView:
        raise NotImplementedError
