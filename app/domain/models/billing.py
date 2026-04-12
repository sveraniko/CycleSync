from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.db.base import BaseModel, SchemaTableMixin


class Checkout(SchemaTableMixin, BaseModel):
    __tablename__ = "checkouts"
    __schema_name__ = "billing"

    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    checkout_status: Mapped[str] = mapped_column(String(24), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    subtotal_amount: Mapped[int] = mapped_column(Integer(), nullable=False)
    discount_amount: Mapped[int] = mapped_column(Integer(), nullable=False)
    total_amount: Mapped[int] = mapped_column(Integer(), nullable=False)
    settlement_mode: Mapped[str] = mapped_column(String(24), nullable=False)
    source_context: Mapped[str | None] = mapped_column(String(64), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_billing_checkouts_user_status", "user_id", "checkout_status"),
        Index("ix_billing_checkouts_created_at", "created_at"),
        {"schema": "billing"},
    )


class CheckoutItem(SchemaTableMixin, BaseModel):
    __tablename__ = "checkout_items"
    __schema_name__ = "billing"

    checkout_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("billing.checkouts.id", ondelete="CASCADE"),
        nullable=False,
    )
    offer_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("billing.sellable_offers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    offer_code: Mapped[str] = mapped_column(String(64), nullable=False)
    item_code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    qty: Mapped[int] = mapped_column(Integer(), nullable=False)
    unit_amount: Mapped[int] = mapped_column(Integer(), nullable=False)
    line_total: Mapped[int] = mapped_column(Integer(), nullable=False)

    __table_args__ = ({"schema": "billing"},)


class Coupon(SchemaTableMixin, BaseModel):
    __tablename__ = "coupons"
    __schema_name__ = "billing"

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    discount_type: Mapped[str] = mapped_column(String(24), nullable=False)
    discount_value: Mapped[int] = mapped_column(Integer(), nullable=False)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    max_redemptions_total: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    max_redemptions_per_user: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    redeemed_count: Mapped[int] = mapped_column(Integer(), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    grants_free_checkout: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)

    __table_args__ = (
        Index("ix_billing_coupons_status_valid_to", "status", "valid_to"),
        {"schema": "billing"},
    )


class CouponRedemption(SchemaTableMixin, BaseModel):
    __tablename__ = "coupon_redemptions"
    __schema_name__ = "billing"

    coupon_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("billing.coupons.id", ondelete="CASCADE"),
        nullable=False,
    )
    checkout_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("billing.checkouts.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    redeemed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    result_status: Mapped[str] = mapped_column(String(24), nullable=False)
    result_reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    discount_amount: Mapped[int] = mapped_column(Integer(), nullable=False)
    final_total_after_discount: Mapped[int] = mapped_column(Integer(), nullable=False)

    __table_args__ = (
        Index("ix_billing_coupon_redemptions_coupon_user", "coupon_id", "user_id"),
        Index("ix_billing_coupon_redemptions_checkout", "checkout_id"),
        {"schema": "billing"},
    )


class PaymentAttempt(SchemaTableMixin, BaseModel):
    __tablename__ = "payment_attempts"
    __schema_name__ = "billing"

    checkout_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("billing.checkouts.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider_code: Mapped[str] = mapped_column(String(64), nullable=False)
    attempt_status: Mapped[str] = mapped_column(String(24), nullable=False)
    requested_amount: Mapped[int] = mapped_column(Integer(), nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)

    __table_args__ = (
        Index("ix_billing_payment_attempts_checkout", "checkout_id"),
        {"schema": "billing"},
    )


class PaymentProviderSession(SchemaTableMixin, BaseModel):
    __tablename__ = "payment_provider_sessions"
    __schema_name__ = "billing"

    checkout_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("billing.checkouts.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider_code: Mapped[str] = mapped_column(String(64), nullable=False)
    session_payload_json: Mapped[dict] = mapped_column(JSONB(), nullable=False)
    session_status: Mapped[str] = mapped_column(String(24), nullable=False)

    __table_args__ = (
        Index("ix_billing_provider_sessions_checkout", "checkout_id"),
        {"schema": "billing"},
    )


class SellableOffer(SchemaTableMixin, BaseModel):
    __tablename__ = "sellable_offers"
    __schema_name__ = "billing"

    offer_code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    default_amount: Mapped[int] = mapped_column(Integer(), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)

    __table_args__ = (
        Index("ix_billing_sellable_offers_status", "status"),
        Index("ix_billing_sellable_offers_code", "offer_code"),
        UniqueConstraint("offer_code", name="uq_billing_sellable_offers_offer_code"),
        {"schema": "billing"},
    )


class OfferEntitlement(SchemaTableMixin, BaseModel):
    __tablename__ = "offer_entitlements"
    __schema_name__ = "billing"

    offer_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("billing.sellable_offers.id", ondelete="CASCADE"),
        nullable=False,
    )
    entitlement_code: Mapped[str] = mapped_column(String(64), nullable=False)
    grant_duration_days: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    qty: Mapped[int | None] = mapped_column(Integer(), nullable=True)

    __table_args__ = (
        Index("ix_billing_offer_entitlements_offer", "offer_id"),
        Index("ix_billing_offer_entitlements_offer_code", "offer_id", "entitlement_code"),
        UniqueConstraint("offer_id", "entitlement_code", name="uq_billing_offer_entitlements_offer_entitlement"),
        {"schema": "billing"},
    )


class CheckoutFulfillment(SchemaTableMixin, BaseModel):
    __tablename__ = "checkout_fulfillments"
    __schema_name__ = "billing"

    checkout_id: Mapped[PGUUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("billing.checkouts.id", ondelete="CASCADE"),
        nullable=False,
    )
    fulfillment_status: Mapped[str] = mapped_column(String(24), nullable=False)
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result_payload_json: Mapped[dict | None] = mapped_column(JSONB(), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)

    __table_args__ = (
        Index("ix_billing_checkout_fulfillments_checkout", "checkout_id"),
        UniqueConstraint("checkout_id", name="uq_billing_checkout_fulfillments_checkout_id"),
        {"schema": "billing"},
    )
