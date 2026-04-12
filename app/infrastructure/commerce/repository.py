from datetime import datetime
from uuid import UUID

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.application.commerce.repository import CommerceRepository
from app.application.commerce.schemas import (
    CheckoutCreate,
    CheckoutDiagnostics,
    CheckoutFulfillmentView,
    CheckoutItemCreate,
    CheckoutItemView,
    CheckoutStateView,
    CheckoutView,
    CouponCreate,
    CouponRedemptionView,
    CouponView,
    OfferEntitlementView,
    PaymentAttemptView,
    ProviderSessionView,
    SellableOfferView,
)
from app.domain.models.billing import (
    Checkout,
    CheckoutFulfillment,
    CheckoutItem,
    Coupon,
    CouponRedemption,
    OfferEntitlement,
    PaymentAttempt,
    PaymentProviderSession,
    SellableOffer,
)
from app.domain.models.ops import OutboxEvent


class SqlAlchemyCommerceRepository(CommerceRepository):
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self.session_factory = session_factory

    async def create_checkout(self, request: CheckoutCreate, *, now_utc: datetime) -> CheckoutView:
        async with self.session_factory() as session:
            row = Checkout(
                user_id=request.user_id,
                checkout_status="created",
                currency=request.currency,
                subtotal_amount=0,
                discount_amount=0,
                total_amount=0,
                settlement_mode=request.settlement_mode,
                source_context=request.source_context,
                completed_at=None,
                created_at=now_utc,
                updated_at=now_utc,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return self._to_checkout_view(row)

    async def get_sellable_offer_by_code(self, *, offer_code: str) -> SellableOfferView | None:
        async with self.session_factory() as session:
            row = await session.scalar(select(SellableOffer).where(SellableOffer.offer_code == offer_code))
            return self._to_offer_view(row) if row else None

    async def list_sellable_offers(self, *, only_active: bool = True) -> tuple[SellableOfferView, ...]:
        async with self.session_factory() as session:
            stmt = select(SellableOffer).order_by(SellableOffer.offer_code.asc())
            if only_active:
                stmt = stmt.where(SellableOffer.status == "active")
            rows = list(await session.scalars(stmt))
            return tuple(self._to_offer_view(row) for row in rows)

    async def list_offer_entitlements(self, *, offer_ids: tuple[UUID, ...]) -> tuple[OfferEntitlementView, ...]:
        if not offer_ids:
            return ()
        async with self.session_factory() as session:
            rows = list(
                await session.scalars(
                    select(OfferEntitlement)
                    .where(OfferEntitlement.offer_id.in_(offer_ids))
                    .order_by(OfferEntitlement.offer_id.asc(), OfferEntitlement.entitlement_code.asc())
                )
            )
            return tuple(self._to_offer_entitlement_view(row) for row in rows)

    async def add_checkout_items(self, *, checkout_id: UUID, items: tuple[CheckoutItemCreate, ...], now_utc: datetime) -> tuple[CheckoutItemView, ...]:
        async with self.session_factory() as session:
            persisted: list[CheckoutItem] = []
            subtotal = 0
            for item in items:
                offer = await session.scalar(select(SellableOffer).where(SellableOffer.offer_code == item.offer_code, SellableOffer.status == "active"))
                if offer is None:
                    raise ValueError(f"offer_not_found_or_inactive:{item.offer_code}")
                line_total = item.qty * offer.default_amount
                subtotal += line_total
                row = CheckoutItem(
                    checkout_id=checkout_id,
                    offer_id=offer.id,
                    offer_code=offer.offer_code,
                    item_code=offer.offer_code,
                    title=offer.title,
                    qty=item.qty,
                    unit_amount=offer.default_amount,
                    line_total=line_total,
                    created_at=now_utc,
                    updated_at=now_utc,
                )
                persisted.append(row)
                session.add(row)
            checkout = await session.scalar(select(Checkout).where(Checkout.id == checkout_id))
            if checkout is not None:
                checkout.subtotal_amount = subtotal
                checkout.total_amount = max(subtotal - checkout.discount_amount, 0)
                checkout.updated_at = now_utc
                session.add(checkout)
            await session.commit()
            for row in persisted:
                await session.refresh(row)
            return tuple(self._to_item_view(row) for row in persisted)

    async def get_checkout(self, *, checkout_id: UUID) -> CheckoutStateView | None:
        async with self.session_factory() as session:
            checkout = await session.scalar(select(Checkout).where(Checkout.id == checkout_id))
            if checkout is None:
                return None
            items = list(await session.scalars(select(CheckoutItem).where(CheckoutItem.checkout_id == checkout_id).order_by(CheckoutItem.created_at.asc())))
            attempts = list(await session.scalars(select(PaymentAttempt).where(PaymentAttempt.checkout_id == checkout_id).order_by(PaymentAttempt.created_at.asc())))
            fulfillment = await session.scalar(select(CheckoutFulfillment).where(CheckoutFulfillment.checkout_id == checkout_id))
            return CheckoutStateView(
                checkout=self._to_checkout_view(checkout),
                items=tuple(self._to_item_view(item) for item in items),
                attempts=tuple(self._to_attempt_view(item) for item in attempts),
                fulfillment=self._to_fulfillment_view(fulfillment) if fulfillment else None,
            )

    async def mark_checkout_status(self, *, checkout_id: UUID, checkout_status: str, now_utc: datetime, completed_at: datetime | None = None) -> CheckoutView | None:
        async with self.session_factory() as session:
            row = await session.scalar(select(Checkout).where(Checkout.id == checkout_id))
            if row is None:
                return None
            row.checkout_status = checkout_status
            row.updated_at = now_utc
            if completed_at is not None:
                row.completed_at = completed_at
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return self._to_checkout_view(row)

    async def update_checkout_amounts(self, *, checkout_id: UUID, discount_amount: int, total_amount: int, now_utc: datetime) -> CheckoutView | None:
        async with self.session_factory() as session:
            row = await session.scalar(select(Checkout).where(Checkout.id == checkout_id))
            if row is None:
                return None
            row.discount_amount = discount_amount
            row.total_amount = total_amount
            row.updated_at = now_utc
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return self._to_checkout_view(row)

    async def create_coupon(self, request: CouponCreate, *, now_utc: datetime) -> CouponView:
        async with self.session_factory() as session:
            row = Coupon(
                code=request.code,
                status="active",
                discount_type=request.discount_type,
                discount_value=request.discount_value,
                currency=request.currency,
                valid_from=request.valid_from,
                valid_to=request.valid_to,
                max_redemptions_total=request.max_redemptions_total,
                max_redemptions_per_user=request.max_redemptions_per_user,
                redeemed_count=0,
                notes=request.notes,
                grants_free_checkout=False,
                created_at=now_utc,
                updated_at=now_utc,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return self._to_coupon_view(row)

    async def get_coupon_by_code(self, *, code: str) -> CouponView | None:
        async with self.session_factory() as session:
            row = await session.scalar(select(Coupon).where(Coupon.code == code))
            return self._to_coupon_view(row) if row else None

    async def get_coupon(self, *, coupon_id: UUID) -> CouponView | None:
        async with self.session_factory() as session:
            row = await session.scalar(select(Coupon).where(Coupon.id == coupon_id))
            return self._to_coupon_view(row) if row else None

    async def disable_coupon(self, *, coupon_id: UUID, now_utc: datetime) -> CouponView | None:
        async with self.session_factory() as session:
            row = await session.scalar(select(Coupon).where(Coupon.id == coupon_id))
            if row is None:
                return None
            row.status = "disabled"
            row.updated_at = now_utc
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return self._to_coupon_view(row)

    async def list_coupon_redemptions(self, *, coupon_id: UUID) -> tuple[CouponRedemptionView, ...]:
        async with self.session_factory() as session:
            rows = list(await session.scalars(select(CouponRedemption).where(CouponRedemption.coupon_id == coupon_id).order_by(CouponRedemption.redeemed_at.desc())))
            return tuple(self._to_coupon_redemption_view(row) for row in rows)

    async def count_coupon_success_redemptions(self, *, coupon_id: UUID, user_id: str | None = None) -> int:
        async with self.session_factory() as session:
            query = select(func.count()).select_from(CouponRedemption).where(CouponRedemption.coupon_id == coupon_id, CouponRedemption.result_status == "applied")
            if user_id is not None:
                query = query.where(CouponRedemption.user_id == user_id)
            value = await session.scalar(query)
            return int(value or 0)

    async def get_applied_coupon_redemption(self, *, checkout_id: UUID, coupon_id: UUID) -> CouponRedemptionView | None:
        async with self.session_factory() as session:
            row = await session.scalar(select(CouponRedemption).where(CouponRedemption.checkout_id == checkout_id, CouponRedemption.coupon_id == coupon_id, CouponRedemption.result_status == "applied"))
            return self._to_coupon_redemption_view(row) if row else None

    async def create_coupon_redemption(self, *, coupon_id: UUID, checkout_id: UUID, user_id: str, redeemed_at: datetime, result_status: str, result_reason_code: str | None, discount_amount: int, final_total_after_discount: int) -> CouponRedemptionView:
        async with self.session_factory() as session:
            row = CouponRedemption(
                coupon_id=coupon_id,
                checkout_id=checkout_id,
                user_id=user_id,
                redeemed_at=redeemed_at,
                result_status=result_status,
                result_reason_code=result_reason_code,
                discount_amount=discount_amount,
                final_total_after_discount=final_total_after_discount,
                created_at=redeemed_at,
                updated_at=redeemed_at,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return self._to_coupon_redemption_view(row)

    async def increment_coupon_redemption_count(self, *, coupon_id: UUID, now_utc: datetime) -> CouponView | None:
        async with self.session_factory() as session:
            row = await session.scalar(select(Coupon).where(Coupon.id == coupon_id))
            if row is None:
                return None
            row.redeemed_count += 1
            if row.max_redemptions_total is not None and row.redeemed_count >= row.max_redemptions_total:
                row.status = "exhausted"
            row.updated_at = now_utc
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return self._to_coupon_view(row)

    async def create_payment_attempt(self, *, checkout_id: UUID, provider_code: str, requested_amount: int, attempt_status: str, now_utc: datetime, provider_reference: str | None = None, error_code: str | None = None, error_message: str | None = None) -> PaymentAttemptView:
        async with self.session_factory() as session:
            row = PaymentAttempt(
                checkout_id=checkout_id,
                provider_code=provider_code,
                attempt_status=attempt_status,
                requested_amount=requested_amount,
                provider_reference=provider_reference,
                error_code=error_code,
                error_message=error_message,
                created_at=now_utc,
                updated_at=now_utc,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return self._to_attempt_view(row)

    async def update_payment_attempt(self, *, attempt_id: UUID, attempt_status: str, now_utc: datetime, provider_reference: str | None = None, error_code: str | None = None, error_message: str | None = None) -> PaymentAttemptView | None:
        async with self.session_factory() as session:
            row = await session.scalar(select(PaymentAttempt).where(PaymentAttempt.id == attempt_id))
            if row is None:
                return None
            row.attempt_status = attempt_status
            row.provider_reference = provider_reference
            row.error_code = error_code
            row.error_message = error_message
            row.updated_at = now_utc
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return self._to_attempt_view(row)

    async def create_provider_session(self, *, checkout_id: UUID, provider_code: str, session_status: str, session_payload: dict, now_utc: datetime) -> ProviderSessionView:
        async with self.session_factory() as session:
            row = PaymentProviderSession(
                checkout_id=checkout_id,
                provider_code=provider_code,
                session_status=session_status,
                session_payload_json=session_payload,
                created_at=now_utc,
                updated_at=now_utc,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return ProviderSessionView(provider_session_id=row.id, checkout_id=row.checkout_id, provider_code=row.provider_code, session_status=row.session_status, session_payload=row.session_payload_json)

    async def get_checkout_fulfillment(self, *, checkout_id: UUID) -> CheckoutFulfillmentView | None:
        async with self.session_factory() as session:
            row = await session.scalar(select(CheckoutFulfillment).where(CheckoutFulfillment.checkout_id == checkout_id))
            return self._to_fulfillment_view(row) if row else None

    async def upsert_checkout_fulfillment(self, *, checkout_id: UUID, fulfillment_status: str, now_utc: datetime, fulfilled_at: datetime | None = None, result_payload: dict | None = None, error_code: str | None = None, error_message: str | None = None) -> CheckoutFulfillmentView:
        async with self.session_factory() as session:
            row = await session.scalar(select(CheckoutFulfillment).where(CheckoutFulfillment.checkout_id == checkout_id))
            if row is None:
                row = CheckoutFulfillment(
                    checkout_id=checkout_id,
                    fulfillment_status=fulfillment_status,
                    fulfilled_at=fulfilled_at,
                    result_payload_json=result_payload,
                    error_code=error_code,
                    error_message=error_message,
                    created_at=now_utc,
                    updated_at=now_utc,
                )
            else:
                row.fulfillment_status = fulfillment_status
                row.fulfilled_at = fulfilled_at
                row.result_payload_json = result_payload
                row.error_code = error_code
                row.error_message = error_message
                row.updated_at = now_utc
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return self._to_fulfillment_view(row)

    async def get_diagnostics(self, *, commerce_mode: str, provider_summary: dict[str, dict[str, object]]) -> CheckoutDiagnostics:
        async with self.session_factory() as session:
            pending = await session.scalar(select(func.count()).select_from(Checkout).where(Checkout.checkout_status.in_(["created", "awaiting_payment"])))
            completed = await session.scalar(select(func.count()).select_from(Checkout).where(Checkout.checkout_status == "completed"))
            failed = await session.scalar(select(func.count()).select_from(Checkout).where(Checkout.checkout_status == "failed"))
            free_settlements = await session.scalar(select(func.count()).select_from(PaymentAttempt).where(PaymentAttempt.provider_code == "free", PaymentAttempt.attempt_status == "succeeded"))
            active_coupons = await session.scalar(select(func.count()).select_from(Coupon).where(Coupon.status == "active"))
            exhausted_coupons = await session.scalar(select(func.count()).select_from(Coupon).where(Coupon.status == "exhausted"))
            coupon_redemptions = await session.scalar(select(func.count()).select_from(CouponRedemption).where(CouponRedemption.result_status == "applied"))
            coupon_free_settlements = await session.scalar(
                select(func.count(distinct(PaymentAttempt.checkout_id)))
                .select_from(PaymentAttempt)
                .join(CouponRedemption, CouponRedemption.checkout_id == PaymentAttempt.checkout_id)
                .where(
                    PaymentAttempt.provider_code == "free",
                    PaymentAttempt.attempt_status == "succeeded",
                    CouponRedemption.result_status == "applied",
                    CouponRedemption.final_total_after_discount == 0,
                )
            )
            attempt_rows = await session.execute(
                select(PaymentAttempt.provider_code, func.count())
                .group_by(PaymentAttempt.provider_code)
            )
            succeeded_rows = await session.execute(
                select(PaymentAttempt.provider_code, func.count())
                .where(PaymentAttempt.attempt_status == "succeeded")
                .group_by(PaymentAttempt.provider_code)
            )
            failed_rows = await session.execute(
                select(PaymentAttempt.provider_code, func.count())
                .where(PaymentAttempt.attempt_status.in_(["failed", "cancelled", "expired"]))
                .group_by(PaymentAttempt.provider_code)
            )
            return CheckoutDiagnostics(
                commerce_mode=commerce_mode,
                provider_summary=provider_summary,
                pending_checkouts=int(pending or 0),
                completed_checkouts=int(completed or 0),
                failed_checkouts=int(failed or 0),
                free_settlements=int(free_settlements or 0),
                active_coupons=int(active_coupons or 0),
                exhausted_coupons=int(exhausted_coupons or 0),
                coupon_redemptions=int(coupon_redemptions or 0),
                coupon_free_settlements=int(coupon_free_settlements or 0),
                provider_attempts={row[0]: int(row[1]) for row in attempt_rows},
                provider_succeeded={row[0]: int(row[1]) for row in succeeded_rows},
                provider_failed={row[0]: int(row[1]) for row in failed_rows},
            )

    async def enqueue_event(self, *, event_type: str, aggregate_type: str, aggregate_id: UUID, payload: dict) -> None:
        async with self.session_factory() as session:
            session.add(OutboxEvent(event_type=event_type, aggregate_type=aggregate_type, aggregate_id=aggregate_id, payload_json=payload, status="pending"))
            await session.commit()

    @staticmethod
    def _to_checkout_view(row: Checkout) -> CheckoutView:
        return CheckoutView(
            checkout_id=row.id,
            user_id=row.user_id,
            checkout_status=row.checkout_status,
            currency=row.currency,
            subtotal_amount=row.subtotal_amount,
            discount_amount=row.discount_amount,
            total_amount=row.total_amount,
            settlement_mode=row.settlement_mode,
            source_context=row.source_context,
            created_at=row.created_at,
            updated_at=row.updated_at,
            completed_at=row.completed_at,
        )

    @staticmethod
    def _to_item_view(row: CheckoutItem) -> CheckoutItemView:
        return CheckoutItemView(
            checkout_item_id=row.id,
            checkout_id=row.checkout_id,
            offer_id=row.offer_id,
            offer_code=row.offer_code,
            item_code=row.item_code,
            title=row.title,
            qty=row.qty,
            unit_amount=row.unit_amount,
            line_total=row.line_total,
        )

    @staticmethod
    def _to_offer_view(row: SellableOffer) -> SellableOfferView:
        return SellableOfferView(
            offer_id=row.id,
            offer_code=row.offer_code,
            title=row.title,
            status=row.status,
            currency=row.currency,
            default_amount=row.default_amount,
            description=row.description,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _to_offer_entitlement_view(row: OfferEntitlement) -> OfferEntitlementView:
        return OfferEntitlementView(
            offer_id=row.offer_id,
            entitlement_code=row.entitlement_code,
            grant_duration_days=row.grant_duration_days,
            qty=row.qty,
        )

    @staticmethod
    def _to_fulfillment_view(row: CheckoutFulfillment) -> CheckoutFulfillmentView:
        return CheckoutFulfillmentView(
            fulfillment_id=row.id,
            checkout_id=row.checkout_id,
            fulfillment_status=row.fulfillment_status,
            fulfilled_at=row.fulfilled_at,
            result_payload=row.result_payload_json,
            error_code=row.error_code,
            error_message=row.error_message,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _to_coupon_view(row: Coupon) -> CouponView:
        return CouponView(
            coupon_id=row.id,
            code=row.code,
            status=row.status,
            discount_type=row.discount_type,
            discount_value=row.discount_value,
            currency=row.currency,
            valid_from=row.valid_from,
            valid_to=row.valid_to,
            max_redemptions_total=row.max_redemptions_total,
            max_redemptions_per_user=row.max_redemptions_per_user,
            redeemed_count=row.redeemed_count,
            notes=row.notes,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _to_coupon_redemption_view(row: CouponRedemption) -> CouponRedemptionView:
        return CouponRedemptionView(
            redemption_id=row.id,
            coupon_id=row.coupon_id,
            checkout_id=row.checkout_id,
            user_id=row.user_id,
            redeemed_at=row.redeemed_at,
            result_status=row.result_status,
            result_reason_code=row.result_reason_code,
            discount_amount=row.discount_amount,
            final_total_after_discount=row.final_total_after_discount,
        )

    @staticmethod
    def _to_attempt_view(row: PaymentAttempt) -> PaymentAttemptView:
        return PaymentAttemptView(
            attempt_id=row.id,
            checkout_id=row.checkout_id,
            provider_code=row.provider_code,
            attempt_status=row.attempt_status,
            requested_amount=row.requested_amount,
            provider_reference=row.provider_reference,
            error_code=row.error_code,
            error_message=row.error_message,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
