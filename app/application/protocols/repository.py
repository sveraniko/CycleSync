from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.application.protocols.schemas import (
    ActiveProtocolView,
    AddProductToDraftResult,
    DraftSettingsInput,
    DraftSettingsView,
    DraftView,
    InventoryConstraintInput,
    InventoryConstraintView,
    PulsePlanPreviewPersistPayload,
    PulsePlanPreviewView,
    PulsePlanEntry,
    PulseProductProfile,
    StackInputTargetInput,
    StackInputTargetView,
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
    concentration_mg_ml: Decimal | None = None
    package_kind: str | None = None
    volume_per_package_ml: Decimal | None = None
    unit_strength_mg: Decimal | None = None


@dataclass(slots=True)
class EstimatorProductMetadata:
    product_id: UUID
    product_name: str
    package_kind: str | None
    units_per_package: Decimal | None
    volume_per_package_ml: Decimal | None
    unit_strength_mg: Decimal | None


@dataclass(slots=True)
class CourseEstimateSourceData:
    source_type: str
    preview_id: UUID | None
    protocol_id: UUID | None
    draft_id: UUID | None
    protocol_input_mode: str | None
    duration_weeks: int | None
    entries: list[PulsePlanEntry]
    inventory_constraints: list[InventoryConstraintView]
    product_metadata: dict[UUID, EstimatorProductMetadata]


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

    async def upsert_stack_input_targets(self, draft_id: UUID, targets: list[StackInputTargetInput]) -> list[StackInputTargetView]:
        raise NotImplementedError

    async def list_stack_input_targets(
        self, draft_id: UUID, protocol_input_mode: str | None = None
    ) -> list[StackInputTargetView]:
        raise NotImplementedError

    async def upsert_inventory_constraints(
        self, draft_id: UUID, constraints: list[InventoryConstraintInput]
    ) -> list[InventoryConstraintView]:
        raise NotImplementedError

    async def list_inventory_constraints(
        self, draft_id: UUID, protocol_input_mode: str | None = None
    ) -> list[InventoryConstraintView]:
        raise NotImplementedError

    async def has_successful_preview_for_draft(self, draft_id: UUID) -> bool:
        raise NotImplementedError

    async def create_pulse_plan_preview(self, payload: PulsePlanPreviewPersistPayload) -> PulsePlanPreviewView:
        raise NotImplementedError

    async def promote_latest_preview_to_active(self, user_id: str) -> ActiveProtocolView:
        raise NotImplementedError

    async def cancel_active_protocol(self, user_id: str) -> UUID | None:
        raise NotImplementedError

    async def get_course_estimate_source_from_preview(self, preview_id: UUID) -> CourseEstimateSourceData | None:
        raise NotImplementedError

    async def get_course_estimate_source_from_active_protocol(self, protocol_id: UUID) -> CourseEstimateSourceData | None:
        raise NotImplementedError
