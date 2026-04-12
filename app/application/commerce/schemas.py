from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

COMMERCE_MODES = {"disabled", "test", "live"}
CHECKOUT_STATUSES = {"created", "awaiting_payment", "completed", "failed", "blocked"}
PAYMENT_ATTEMPT_STATUSES = {"started", "succeeded", "failed"}
FREE_REASON_CODES = {"dev_mode", "gift_coupon", "manual_free_checkout", "ops_test"}


@dataclass(slots=True)
class CheckoutItemCreate:
    item_code: str
    title: str
    qty: int
    unit_amount: int


@dataclass(slots=True)
class CheckoutCreate:
    user_id: str
    currency: str
    settlement_mode: str
    source_context: str | None = None


@dataclass(slots=True)
class CheckoutView:
    checkout_id: UUID
    user_id: str
    checkout_status: str
    currency: str
    subtotal_amount: int
    discount_amount: int
    total_amount: int
    settlement_mode: str
    source_context: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


@dataclass(slots=True)
class CheckoutItemView:
    checkout_item_id: UUID
    checkout_id: UUID
    item_code: str
    title: str
    qty: int
    unit_amount: int
    line_total: int


@dataclass(slots=True)
class PaymentAttemptView:
    attempt_id: UUID
    checkout_id: UUID
    provider_code: str
    attempt_status: str
    requested_amount: int
    provider_reference: str | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class ProviderSessionView:
    provider_session_id: UUID
    checkout_id: UUID
    provider_code: str
    session_status: str
    session_payload: dict


@dataclass(slots=True)
class CheckoutStateView:
    checkout: CheckoutView
    items: tuple[CheckoutItemView, ...]
    attempts: tuple[PaymentAttemptView, ...]


@dataclass(slots=True)
class CheckoutDiagnostics:
    commerce_mode: str
    provider_summary: dict[str, dict[str, object]]
    pending_checkouts: int
    completed_checkouts: int
    failed_checkouts: int
    free_settlements: int
