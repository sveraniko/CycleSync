from datetime import datetime, timezone
from uuid import UUID

from app.application.commerce.providers import PaymentProviderRegistry
from app.application.commerce.repository import CommerceRepository
from app.application.commerce.fulfillment import CheckoutFulfillmentService
from app.application.commerce.schemas import (
    CHECKOUT_STATUSES,
    COMMERCE_MODES,
    COUPON_DISCOUNT_TYPES,
    COUPON_STATUSES,
    FREE_REASON_CODES,
    CheckoutCreate,
    CheckoutItemCreate,
    CheckoutStateView,
    CouponApplyResult,
    CouponCreate,
    CouponRedemptionView,
    CouponView,
)


class CommerceError(ValueError):
    pass


class CheckoutService:
    def __init__(
        self,
        repository: CommerceRepository,
        provider_registry: PaymentProviderRegistry,
        commerce_mode: str,
        fulfillment_service: CheckoutFulfillmentService | None = None,
    ) -> None:
        if commerce_mode not in COMMERCE_MODES:
            raise CommerceError(f"unsupported_commerce_mode:{commerce_mode}")
        self.repository = repository
        self.provider_registry = provider_registry
        self.commerce_mode = commerce_mode
        self.fulfillment_service = fulfillment_service

    async def create_checkout(
        self,
        *,
        user_id: str,
        currency: str,
        items: tuple[CheckoutItemCreate, ...],
        settlement_mode: str,
        source_context: str | None = None,
        now_utc: datetime | None = None,
    ) -> CheckoutStateView:
        now = now_utc or datetime.now(timezone.utc)
        checkout = await self.repository.create_checkout(
            CheckoutCreate(
                user_id=user_id,
                currency=currency,
                settlement_mode=settlement_mode,
                source_context=source_context,
            ),
            now_utc=now,
        )
        try:
            saved_items = await self.repository.add_checkout_items(checkout_id=checkout.checkout_id, items=items, now_utc=now)
        except ValueError as exc:
            raise CommerceError(str(exc)) from exc
        subtotal = sum(item.line_total for item in saved_items)
        await self.repository.mark_checkout_status(
            checkout_id=checkout.checkout_id,
            checkout_status="created",
            now_utc=now,
        )
        await self.repository.enqueue_event(
            event_type="checkout_created",
            aggregate_type="checkout",
            aggregate_id=checkout.checkout_id,
            payload={
                "user_id": user_id,
                "source_context": source_context,
                "subtotal_amount": subtotal,
                "currency": currency,
            },
        )
        return await self.get_checkout(checkout_id=checkout.checkout_id)

    async def create_coupon(self, request: CouponCreate, *, now_utc: datetime | None = None) -> CouponView:
        now = now_utc or datetime.now(timezone.utc)
        if request.discount_type not in COUPON_DISCOUNT_TYPES:
            raise CommerceError(f"unsupported_discount_type:{request.discount_type}")
        code = request.code.strip().upper()
        if not code:
            raise CommerceError("coupon_code_required")
        if request.discount_type == "percent" and (request.discount_value <= 0 or request.discount_value > 100):
            raise CommerceError("invalid_percent_discount")
        if request.discount_type == "fixed" and request.discount_value <= 0:
            raise CommerceError("invalid_fixed_discount")
        if request.discount_type == "fixed" and not request.currency:
            raise CommerceError("fixed_discount_currency_required")
        if request.valid_from and request.valid_to and request.valid_from > request.valid_to:
            raise CommerceError("invalid_coupon_validity_window")
        created = await self.repository.create_coupon(
            CouponCreate(
                code=code,
                discount_type=request.discount_type,
                discount_value=request.discount_value,
                currency=request.currency.upper() if request.currency else None,
                valid_from=request.valid_from,
                valid_to=request.valid_to,
                max_redemptions_total=request.max_redemptions_total,
                max_redemptions_per_user=request.max_redemptions_per_user,
                notes=request.notes,
            ),
            now_utc=now,
        )
        await self.repository.enqueue_event(
            event_type="coupon_created",
            aggregate_type="coupon",
            aggregate_id=created.coupon_id,
            payload={
                "code": created.code,
                "discount_type": created.discount_type,
                "discount_value": created.discount_value,
                "currency": created.currency,
            },
        )
        return created

    async def disable_coupon(self, *, coupon_code: str, now_utc: datetime | None = None) -> CouponView:
        now = now_utc or datetime.now(timezone.utc)
        coupon = await self.repository.get_coupon_by_code(code=coupon_code.strip().upper())
        if coupon is None:
            raise CommerceError("coupon_not_found")
        disabled = await self.repository.disable_coupon(coupon_id=coupon.coupon_id, now_utc=now)
        if disabled is None:
            raise CommerceError("coupon_not_found")
        await self.repository.enqueue_event(
            event_type="coupon_disabled",
            aggregate_type="coupon",
            aggregate_id=disabled.coupon_id,
            payload={"code": disabled.code},
        )
        return disabled

    async def inspect_coupon(self, *, coupon_code: str) -> CouponView | None:
        return await self.repository.get_coupon_by_code(code=coupon_code.strip().upper())

    async def list_coupon_redemptions(self, *, coupon_code: str) -> tuple[CouponRedemptionView, ...]:
        coupon = await self.repository.get_coupon_by_code(code=coupon_code.strip().upper())
        if coupon is None:
            raise CommerceError("coupon_not_found")
        return await self.repository.list_coupon_redemptions(coupon_id=coupon.coupon_id)

    async def apply_coupon_to_checkout(
        self,
        *,
        checkout_id: UUID,
        user_id: str,
        coupon_code: str,
        now_utc: datetime | None = None,
    ) -> CouponApplyResult:
        now = now_utc or datetime.now(timezone.utc)
        state = await self.get_checkout(checkout_id=checkout_id)
        normalized_code = coupon_code.strip().upper()
        coupon = await self.repository.get_coupon_by_code(code=normalized_code)
        if coupon is None:
            await self.repository.enqueue_event(
                event_type="coupon_application_failed",
                aggregate_type="checkout",
                aggregate_id=checkout_id,
                payload={"coupon_code": normalized_code, "reason_code": "coupon_not_found"},
            )
            return CouponApplyResult(status="denied", reason_code="coupon_not_found", checkout=state, coupon=None, redemption=None)

        existing = await self.repository.get_applied_coupon_redemption(checkout_id=checkout_id, coupon_id=coupon.coupon_id)
        if existing is not None:
            return CouponApplyResult(status="already_applied", reason_code="already_applied", checkout=state, coupon=coupon, redemption=existing)

        denial_reason = self._resolve_coupon_denial(coupon=coupon, checkout=state, user_id=user_id, now_utc=now)
        if denial_reason is None:
            user_success_count = await self.repository.count_coupon_success_redemptions(coupon_id=coupon.coupon_id, user_id=user_id)
            total_success_count = await self.repository.count_coupon_success_redemptions(coupon_id=coupon.coupon_id)
            if coupon.max_redemptions_per_user is not None and user_success_count >= coupon.max_redemptions_per_user:
                denial_reason = "per_user_limit_reached"
            elif coupon.max_redemptions_total is not None and total_success_count >= coupon.max_redemptions_total:
                denial_reason = "coupon_exhausted"

        if denial_reason is not None:
            redemption = await self.repository.create_coupon_redemption(
                coupon_id=coupon.coupon_id,
                checkout_id=checkout_id,
                user_id=user_id,
                redeemed_at=now,
                result_status="denied",
                result_reason_code=denial_reason,
                discount_amount=0,
                final_total_after_discount=state.checkout.total_amount,
            )
            await self.repository.enqueue_event(
                event_type="coupon_application_failed",
                aggregate_type="checkout",
                aggregate_id=checkout_id,
                payload={"coupon_code": coupon.code, "coupon_id": str(coupon.coupon_id), "reason_code": denial_reason},
            )
            refreshed = await self.get_checkout(checkout_id=checkout_id)
            return CouponApplyResult(status="denied", reason_code=denial_reason, checkout=refreshed, coupon=coupon, redemption=redemption)

        discount_amount = self._calculate_discount_amount(coupon=coupon, checkout=state)
        final_total = max(state.checkout.subtotal_amount - discount_amount, 0)
        await self.repository.update_checkout_amounts(
            checkout_id=checkout_id,
            discount_amount=discount_amount,
            total_amount=final_total,
            now_utc=now,
        )
        redemption = await self.repository.create_coupon_redemption(
            coupon_id=coupon.coupon_id,
            checkout_id=checkout_id,
            user_id=user_id,
            redeemed_at=now,
            result_status="applied",
            result_reason_code="applied",
            discount_amount=discount_amount,
            final_total_after_discount=final_total,
        )
        updated_coupon = await self.repository.increment_coupon_redemption_count(coupon_id=coupon.coupon_id, now_utc=now)
        await self.repository.enqueue_event(
            event_type="coupon_applied",
            aggregate_type="checkout",
            aggregate_id=checkout_id,
            payload={
                "coupon_id": str(coupon.coupon_id),
                "coupon_code": coupon.code,
                "discount_amount": discount_amount,
                "final_total_after_discount": final_total,
            },
        )
        await self.repository.enqueue_event(
            event_type="coupon_redeemed",
            aggregate_type="coupon",
            aggregate_id=coupon.coupon_id,
            payload={
                "checkout_id": str(checkout_id),
                "user_id": user_id,
                "redemption_id": str(redemption.redemption_id),
                "result_status": "applied",
            },
        )
        refreshed = await self.get_checkout(checkout_id=checkout_id)
        return CouponApplyResult(status="applied", reason_code=None, checkout=refreshed, coupon=updated_coupon or coupon, redemption=redemption)

    def _resolve_coupon_denial(self, *, coupon: CouponView, checkout: CheckoutStateView, user_id: str, now_utc: datetime) -> str | None:
        _ = user_id
        if coupon.status not in COUPON_STATUSES:
            return "invalid_coupon_status"
        if coupon.status == "disabled":
            return "coupon_disabled"
        if coupon.status == "expired":
            return "coupon_expired"
        if coupon.status == "exhausted":
            return "coupon_exhausted"
        if coupon.valid_from and now_utc < coupon.valid_from:
            return "coupon_not_started"
        if coupon.valid_to and now_utc > coupon.valid_to:
            return "coupon_expired"
        if coupon.discount_type == "fixed" and coupon.currency and coupon.currency != checkout.checkout.currency:
            return "currency_mismatch"
        return None

    def _calculate_discount_amount(self, *, coupon: CouponView, checkout: CheckoutStateView) -> int:
        subtotal = checkout.checkout.subtotal_amount
        if coupon.discount_type == "percent":
            return min((subtotal * coupon.discount_value) // 100, subtotal)
        return min(coupon.discount_value, subtotal)

    async def initiate_payment(self, *, checkout_id, provider_code: str, now_utc: datetime | None = None) -> CheckoutStateView:
        now = now_utc or datetime.now(timezone.utc)
        state = await self.get_checkout(checkout_id=checkout_id)
        if state.checkout.checkout_status not in CHECKOUT_STATUSES:
            raise CommerceError("unsupported_checkout_status")
        if state.checkout.total_amount <= 0 and provider_code != "free":
            raise CommerceError("zero_total_requires_free_settlement")
        if self.commerce_mode == "disabled":
            await self.repository.mark_checkout_status(checkout_id=checkout_id, checkout_status="blocked", now_utc=now)
            await self.repository.enqueue_event(
                event_type="checkout_mode_blocked",
                aggregate_type="checkout",
                aggregate_id=checkout_id,
                payload={"commerce_mode": self.commerce_mode, "provider_code": provider_code},
            )
            raise CommerceError("commerce_mode_disabled")

        provider = self.provider_registry.get(provider_code)
        if provider is None:
            raise CommerceError(f"provider_not_available:{provider_code}")

        attempt = await self.repository.create_payment_attempt(
            checkout_id=checkout_id,
            provider_code=provider_code,
            requested_amount=state.checkout.total_amount,
            attempt_status="initiated",
            now_utc=now,
        )
        await self.repository.enqueue_event(
            event_type="payment_attempt_started",
            aggregate_type="checkout",
            aggregate_id=checkout_id,
            payload={"attempt_id": str(attempt.attempt_id), "provider_code": provider_code},
        )

        init_data = await provider.initialize_checkout(checkout=state, now_utc=now)
        await self.repository.create_provider_session(
            checkout_id=checkout_id,
            provider_code=provider_code,
            session_status=init_data.session_status,
            session_payload=init_data.session_payload,
            now_utc=now,
        )
        await self.repository.update_payment_attempt(
            attempt_id=attempt.attempt_id,
            attempt_status="pending",
            now_utc=now,
            provider_reference=init_data.provider_reference,
        )
        await self.repository.enqueue_event(
            event_type="payment_provider_session_created",
            aggregate_type="checkout",
            aggregate_id=checkout_id,
            payload={
                "attempt_id": str(attempt.attempt_id),
                "provider_code": provider_code,
                "session_status": init_data.session_status,
            },
        )
        await self.repository.mark_checkout_status(checkout_id=checkout_id, checkout_status="awaiting_payment", now_utc=now)
        return await self.get_checkout(checkout_id=checkout_id)

    async def confirm_provider_payment(
        self,
        *,
        checkout_id: UUID,
        provider_code: str,
        outcome: str = "succeeded",
        metadata: dict | None = None,
        now_utc: datetime | None = None,
    ) -> CheckoutStateView:
        now = now_utc or datetime.now(timezone.utc)
        state = await self.get_checkout(checkout_id=checkout_id)
        provider = self.provider_registry.get(provider_code)
        if provider is None:
            raise CommerceError(f"provider_not_available:{provider_code}")

        target_attempt = None
        for attempt in reversed(state.attempts):
            if attempt.provider_code == provider_code and attempt.attempt_status in {"initiated", "pending", "started"}:
                target_attempt = attempt
                break
        if target_attempt is None:
            raise CommerceError("payment_attempt_not_found")

        settled = await provider.confirm_payment(
            checkout=state,
            now_utc=now,
            metadata={"outcome": outcome, **(metadata or {})},
        )
        if settled.status == "succeeded":
            await self.repository.update_payment_attempt(
                attempt_id=target_attempt.attempt_id,
                attempt_status="succeeded",
                now_utc=now,
                provider_reference=settled.provider_reference,
            )
            await self.repository.mark_checkout_status(
                checkout_id=checkout_id,
                checkout_status="completed",
                now_utc=now,
                completed_at=now,
            )
            await self.repository.enqueue_event(
                event_type="payment_attempt_succeeded",
                aggregate_type="checkout",
                aggregate_id=checkout_id,
                payload={"attempt_id": str(target_attempt.attempt_id), "provider_code": provider_code},
            )
            await self.repository.enqueue_event(
                event_type="checkout_completed",
                aggregate_type="checkout",
                aggregate_id=checkout_id,
                payload={"provider_code": provider_code},
            )
            if self.fulfillment_service is not None:
                await self.fulfillment_service.fulfill_checkout(checkout_id=checkout_id, now_utc=now)
            return await self.get_checkout(checkout_id=checkout_id)

        mapped_status = "failed"
        if settled.status in {"cancelled", "expired"}:
            mapped_status = settled.status
        elif settled.status in {"pending", "initiated"}:
            mapped_status = "pending"
        await self.repository.update_payment_attempt(
            attempt_id=target_attempt.attempt_id,
            attempt_status=mapped_status,
            now_utc=now,
            provider_reference=settled.provider_reference,
            error_code=settled.error_code,
            error_message=settled.error_message,
        )
        if mapped_status in {"failed", "cancelled", "expired"}:
            await self.repository.mark_checkout_status(checkout_id=checkout_id, checkout_status="failed", now_utc=now)
            await self.repository.enqueue_event(
                event_type="payment_attempt_failed",
                aggregate_type="checkout",
                aggregate_id=checkout_id,
                payload={
                    "attempt_id": str(target_attempt.attempt_id),
                    "provider_code": provider_code,
                    "attempt_status": mapped_status,
                    "error_code": settled.error_code,
                },
            )
        return await self.get_checkout(checkout_id=checkout_id)

    async def settle_free_checkout(self, *, checkout_id, reason_code: str, now_utc: datetime | None = None) -> CheckoutStateView:
        now = now_utc or datetime.now(timezone.utc)
        if reason_code not in FREE_REASON_CODES:
            raise CommerceError(f"unsupported_free_reason_code:{reason_code}")
        if reason_code == "gift_coupon":
            state = await self.get_checkout(checkout_id=checkout_id)
            if state.checkout.total_amount != 0:
                raise CommerceError("gift_coupon_requires_zero_total")
        if self.commerce_mode == "disabled":
            raise CommerceError("commerce_mode_disabled")
        if self.commerce_mode == "live":
            raise CommerceError("free_provider_not_allowed_in_live")

        state = await self.get_checkout(checkout_id=checkout_id)
        provider = self.provider_registry.get("free")
        if provider is None:
            raise CommerceError("provider_not_available:free")

        attempt = await self.repository.create_payment_attempt(
            checkout_id=checkout_id,
            provider_code="free",
            requested_amount=state.checkout.total_amount,
            attempt_status="started",
            now_utc=now,
        )
        await self.repository.enqueue_event(
            event_type="payment_attempt_started",
            aggregate_type="checkout",
            aggregate_id=checkout_id,
            payload={"attempt_id": str(attempt.attempt_id), "provider_code": "free"},
        )
        settled = await provider.confirm_payment(checkout=state, now_utc=now, metadata={"reason_code": reason_code})
        if settled.status == "succeeded":
            await self.repository.update_payment_attempt(
                attempt_id=attempt.attempt_id,
                attempt_status="succeeded",
                now_utc=now,
                provider_reference=settled.provider_reference,
            )
            await self.repository.mark_checkout_status(
                checkout_id=checkout_id,
                checkout_status="completed",
                now_utc=now,
                completed_at=now,
            )
            await self.repository.enqueue_event(
                event_type="payment_attempt_succeeded",
                aggregate_type="checkout",
                aggregate_id=checkout_id,
                payload={"attempt_id": str(attempt.attempt_id), "provider_code": "free", "reason_code": reason_code},
            )
            await self.repository.enqueue_event(
                event_type="checkout_completed",
                aggregate_type="checkout",
                aggregate_id=checkout_id,
                payload={"provider_code": "free"},
            )
            await self.repository.enqueue_event(
                event_type="checkout_completed_free",
                aggregate_type="checkout",
                aggregate_id=checkout_id,
                payload={"reason_code": reason_code},
            )
            if self.fulfillment_service is not None:
                await self.fulfillment_service.fulfill_checkout(checkout_id=checkout_id, now_utc=now)
        else:
            await self.repository.update_payment_attempt(
                attempt_id=attempt.attempt_id,
                attempt_status="failed",
                now_utc=now,
                provider_reference=settled.provider_reference,
                error_code=settled.error_code,
                error_message=settled.error_message,
            )
            await self.repository.mark_checkout_status(checkout_id=checkout_id, checkout_status="failed", now_utc=now)
            await self.repository.enqueue_event(
                event_type="payment_attempt_failed",
                aggregate_type="checkout",
                aggregate_id=checkout_id,
                payload={"attempt_id": str(attempt.attempt_id), "provider_code": "free", "error_code": settled.error_code},
            )
        return await self.get_checkout(checkout_id=checkout_id)

    async def get_checkout(self, *, checkout_id) -> CheckoutStateView:
        checkout = await self.repository.get_checkout(checkout_id=checkout_id)
        if checkout is None:
            raise CommerceError("checkout_not_found")
        return checkout

    async def diagnostics(self):
        return await self.repository.get_diagnostics(
            commerce_mode=self.commerce_mode,
            provider_summary=self.provider_registry.diagnostics(),
        )

    async def list_offers(self):
        return await self.repository.list_sellable_offers(only_active=True)
