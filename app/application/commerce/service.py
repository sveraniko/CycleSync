from datetime import datetime, timezone

from app.application.commerce.providers import PaymentProviderRegistry
from app.application.commerce.repository import CommerceRepository
from app.application.commerce.schemas import (
    CHECKOUT_STATUSES,
    COMMERCE_MODES,
    FREE_REASON_CODES,
    CheckoutCreate,
    CheckoutItemCreate,
    CheckoutStateView,
)


class CommerceError(ValueError):
    pass


class CheckoutService:
    def __init__(self, repository: CommerceRepository, provider_registry: PaymentProviderRegistry, commerce_mode: str) -> None:
        if commerce_mode not in COMMERCE_MODES:
            raise CommerceError(f"unsupported_commerce_mode:{commerce_mode}")
        self.repository = repository
        self.provider_registry = provider_registry
        self.commerce_mode = commerce_mode

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
        saved_items = await self.repository.add_checkout_items(checkout_id=checkout.checkout_id, items=items, now_utc=now)
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
        state = await self.get_checkout(checkout_id=checkout.checkout_id)
        if state is None:
            raise CommerceError("checkout_not_found_after_creation")
        return state

    async def initiate_payment(self, *, checkout_id, provider_code: str, now_utc: datetime | None = None) -> CheckoutStateView:
        now = now_utc or datetime.now(timezone.utc)
        state = await self.get_checkout(checkout_id=checkout_id)
        if state.checkout.checkout_status not in CHECKOUT_STATUSES:
            raise CommerceError("unsupported_checkout_status")
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
            attempt_status="started",
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
        await self.repository.mark_checkout_status(checkout_id=checkout_id, checkout_status="awaiting_payment", now_utc=now)
        latest = await self.get_checkout(checkout_id=checkout_id)
        return latest

    async def settle_free_checkout(self, *, checkout_id, reason_code: str, now_utc: datetime | None = None) -> CheckoutStateView:
        now = now_utc or datetime.now(timezone.utc)
        if reason_code not in FREE_REASON_CODES:
            raise CommerceError(f"unsupported_free_reason_code:{reason_code}")
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
        latest = await self.get_checkout(checkout_id=checkout_id)
        return latest

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
