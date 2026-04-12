from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.db.base import BaseModel, SchemaTableMixin


class Entitlement(SchemaTableMixin, BaseModel):
    __tablename__ = "entitlements"
    __schema_name__ = "access"

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean(), nullable=False, server_default=text("true"))

    __table_args__ = (
        UniqueConstraint("code", name="uq_access_entitlements_code"),
        {"schema": "access"},
    )


class EntitlementGrant(SchemaTableMixin, BaseModel):
    __tablename__ = "entitlement_grants"
    __schema_name__ = "access"

    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    entitlement_code: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("access.entitlements.code", ondelete="RESTRICT"),
        nullable=False,
    )
    grant_status: Mapped[str] = mapped_column(String(24), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    granted_by_source: Mapped[str] = mapped_column(String(24), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    replaced_by_grant_id: Mapped[PGUUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)

    __table_args__ = (
        Index("ix_access_entitlement_grants_user_entitlement_status", "user_id", "entitlement_code", "grant_status"),
        Index("ix_access_entitlement_grants_entitlement_status_expires", "entitlement_code", "grant_status", "expires_at"),
        {"schema": "access"},
    )
