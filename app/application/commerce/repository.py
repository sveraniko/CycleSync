from datetime import datetime
from uuid import UUID

from app.application.commerce.schemas import (
    CheckoutCreate,
    CheckoutDiagnostics,
    CheckoutItemCreate,
    CheckoutItemView,
    CheckoutStateView,
    CheckoutView,
    CouponCreate,
    CouponRedemptionView,
    CouponView,
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

    async def update_checkout_amounts(self, *, checkout_id: UUID, discount_amount: int, total_amount: int, now_utc: datetime) -> CheckoutView | None:
        raise NotImplementedError

    async def create_coupon(self, request: CouponCreate, *, now_utc: datetime) -> CouponView:
        raise NotImplementedError

    async def get_coupon_by_code(self, *, code: str) -> CouponView | None:
        raise NotImplementedError

    async def get_coupon(self, *, coupon_id: UUID) -> CouponView | None:
        raise NotImplementedError

    async def disable_coupon(self, *, coupon_id: UUID, now_utc: datetime) -> CouponView | None:
        raise NotImplementedError

    async def list_coupon_redemptions(self, *, coupon_id: UUID) -> tuple[CouponRedemptionView, ...]:
        raise NotImplementedError

    async def count_coupon_success_redemptions(self, *, coupon_id: UUID, user_id: str | None = None) -> int:
        raise NotImplementedError

    async def get_applied_coupon_redemption(self, *, checkout_id: UUID, coupon_id: UUID) -> CouponRedemptionView | None:
        raise NotImplementedError

    async def create_coupon_redemption(
        self,
        *,
        coupon_id: UUID,
        checkout_id: UUID,
        user_id: str,
        redeemed_at: datetime,
        result_status: str,
        result_reason_code: str | None,
        discount_amount: int,
        final_total_after_discount: int,
    ) -> CouponRedemptionView:
        raise NotImplementedError

    async def increment_coupon_redemption_count(self, *, coupon_id: UUID, now_utc: datetime) -> CouponView | None:
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
