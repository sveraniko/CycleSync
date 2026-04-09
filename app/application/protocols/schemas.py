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
    weekly_target_total_mg: Decimal | None = None
    duration_weeks: int | None = None
    preset_code: str | None = None
    max_injection_volume_ml: Decimal | None = None
    max_injections_per_week: int | None = None
    planned_start_date: date | None = None


@dataclass(slots=True)
class DraftSettingsView:
    draft_id: UUID
    weekly_target_total_mg: Decimal | None
    duration_weeks: int | None
    preset_code: str | None
    max_injection_volume_ml: Decimal | None
    max_injections_per_week: int | None
    planned_start_date: date | None
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
