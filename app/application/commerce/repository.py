from datetime import datetime
from uuid import UUID

from app.application.commerce.schemas import (
    CheckoutCreate,
    CheckoutDiagnostics,
    CheckoutItemCreate,
    CheckoutItemView,
    CheckoutStateView,
    CheckoutView,
    PaymentAttemptView,
    ProviderSessionView,
)


class CommerceRepository:
    async def create_checkout(self, request: CheckoutCreate, *, now_utc: datetime) -> CheckoutView:
        raise NotImplementedError

    async def add_checkout_items(self, *, checkout_id: UUID, items: tuple[CheckoutItemCreate, ...], now_utc: datetime) -> tuple[CheckoutItemView, ...]:
        raise NotImplementedError

    async def get_checkout(self, *, checkout_id: UUID) -> CheckoutStateView | None:
        raise NotImplementedError

    async def mark_checkout_status(
        self,
        *,
        checkout_id: UUID,
        checkout_status: str,
        now_utc: datetime,
        completed_at: datetime | None = None,
    ) -> CheckoutView | None:
        raise NotImplementedError

    async def create_payment_attempt(
        self,
        *,
        checkout_id: UUID,
        provider_code: str,
        requested_amount: int,
        attempt_status: str,
        now_utc: datetime,
        provider_reference: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> PaymentAttemptView:
        raise NotImplementedError

    async def update_payment_attempt(
        self,
        *,
        attempt_id: UUID,
        attempt_status: str,
        now_utc: datetime,
        provider_reference: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> PaymentAttemptView | None:
        raise NotImplementedError

    async def create_provider_session(
        self,
        *,
        checkout_id: UUID,
        provider_code: str,
        session_status: str,
        session_payload: dict,
        now_utc: datetime,
    ) -> ProviderSessionView:
        raise NotImplementedError

    async def get_diagnostics(self, *, commerce_mode: str, provider_summary: dict[str, dict[str, object]]) -> CheckoutDiagnostics:
        raise NotImplementedError

    async def enqueue_event(self, *, event_type: str, aggregate_type: str, aggregate_id: UUID, payload: dict) -> None:
        raise NotImplementedError
