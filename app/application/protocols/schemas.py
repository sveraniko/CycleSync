from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID


@dataclass(slots=True)
class DraftItemView:
    item_id: UUID
    draft_id: UUID
    product_id: UUID
    selected_brand: str | None
    selected_product_name: str | None
    notes: str | None
    created_at: datetime


@dataclass(slots=True)
class DraftView:
    draft_id: UUID
    user_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    items: list[DraftItemView]
    settings: "DraftSettingsView | None" = None


@dataclass(slots=True)
class AddProductToDraftResult:
    draft: DraftView
    item: DraftItemView
    added: bool


@dataclass(slots=True)
class DraftSettingsInput:
    protocol_input_mode: str | None = None
    weekly_target_total_mg: Decimal | None = None
    duration_weeks: int | None = None
    preset_code: str | None = None
    max_injection_volume_ml: Decimal | None = None
    max_injections_per_week: int | None = None
    planned_start_date: date | None = None


@dataclass(slots=True)
class DraftSettingsView:
    draft_id: UUID
    protocol_input_mode: str | None
    weekly_target_total_mg: Decimal | None
    duration_weeks: int | None
    preset_code: str | None
    max_injection_volume_ml: Decimal | None
    max_injections_per_week: int | None
    planned_start_date: date | None
    updated_at: datetime


@dataclass(slots=True)
class StackInputTargetInput:
    product_id: UUID
    protocol_input_mode: str
    desired_weekly_mg: Decimal


@dataclass(slots=True)
class StackInputTargetView:
    id: UUID
    draft_id: UUID
    product_id: UUID
    protocol_input_mode: str
    desired_weekly_mg: Decimal
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class DraftReadinessIssue:
    code: str
    message: str
    severity: str
    context: dict | None = None


@dataclass(slots=True)
class DraftReadinessResult:
    draft_id: UUID
    ready: bool
    summary: str
    issues: list[DraftReadinessIssue]


@dataclass(slots=True)
class PulseIngredientProfile:
    ingredient_name: str
    half_life_days: Decimal | None
    amount_mg: Decimal | None
    is_pulse_driver: bool | None
    dose_guidance_min_mg_week: Decimal | None = None
    dose_guidance_max_mg_week: Decimal | None = None
    dose_guidance_typical_mg_week: Decimal | None = None


@dataclass(slots=True)
class PulseProductProfile:
    product_id: UUID
    product_name: str
    concentration_mg_ml: Decimal | None
    max_injection_volume_ml: Decimal | None
    ingredients: list[PulseIngredientProfile]
    package_kind: str | None = None
    units_per_package: Decimal | None = None
    volume_per_package_ml: Decimal | None = None
    unit_strength_mg: Decimal | None = None


@dataclass(slots=True)
class InventoryConstraintInput:
    product_id: UUID
    protocol_input_mode: str
    available_count: Decimal
    count_unit: str


@dataclass(slots=True)
class InventoryConstraintView:
    id: UUID
    draft_id: UUID
    product_id: UUID
    protocol_input_mode: str
    available_count: Decimal
    count_unit: str
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class PulsePlanEntry:
    day_offset: int
    scheduled_day: date | None
    product_id: UUID
    ingredient_context: str | None
    volume_ml: Decimal
    computed_mg: Decimal
    injection_event_key: str
    sequence_no: int


@dataclass(slots=True)
class PulsePlanPreviewPersistPayload:
    draft_id: UUID
    protocol_input_mode: str
    preset_requested: str
    preset_applied: str
    status: str
    degraded_fallback: bool
    settings_snapshot: dict
    summary_metrics: dict | None
    warning_flags: list[str]
    allocation_mode: str | None
    guidance_coverage_score: Decimal | None
    calculation_quality_flags: list[str]
    allocation_details: dict | None
    entries: list[PulsePlanEntry]
    error_message: str | None = None


@dataclass(slots=True)
class PulsePlanPreviewView:
    preview_id: UUID
    draft_id: UUID
    protocol_input_mode: str
    preset_requested: str
    preset_applied: str
    status: str
    degraded_fallback: bool
    summary_metrics: dict | None
    warning_flags: list[str]
    allocation_mode: str | None
    guidance_coverage_score: Decimal | None
    calculation_quality_flags: list[str]
    entries: list[PulsePlanEntry]


@dataclass(slots=True)
class PulseCalculationResult:
    protocol_input_mode: str
    status: str
    preset_requested: str
    preset_applied: str
    degraded_fallback: bool
    warning_flags: list[str]
    summary_metrics: dict | None
    allocation_mode: str | None
    guidance_coverage_score: Decimal | None
    calculation_quality_flags: list[str]
    allocation_details: dict | None
    entries: list[PulsePlanEntry]
    validation_issues: list[str]
    error_message: str | None = None


@dataclass(slots=True)
class ActiveProtocolView:
    protocol_id: UUID
    draft_id: UUID
    source_preview_id: UUID | None
    pulse_plan_id: UUID
    status: str
    settings_snapshot: dict
    protocol_input_mode: str | None
    summary_metrics: dict | None
    warning_flags: list[str]
