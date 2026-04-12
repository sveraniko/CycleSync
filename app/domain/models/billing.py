from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text
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
    item_code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    qty: Mapped[int] = mapped_column(Integer(), nullable=False)
    unit_amount: Mapped[int] = mapped_column(Integer(), nullable=False)
    line_total: Mapped[int] = mapped_column(Integer(), nullable=False)

    __table_args__ = ({"schema": "billing"},)


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
