from datetime import date
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, SmallInteger, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.db.base import BaseModel, SchemaTableMixin


class ProtocolDraft(SchemaTableMixin, BaseModel):
    __tablename__ = "protocol_drafts"
    __schema_name__ = "protocols"

    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")

    items: Mapped[list["ProtocolDraftItem"]] = relationship(
        back_populates="draft",
        cascade="all, delete-orphan",
        order_by="ProtocolDraftItem.created_at",
    )

    __table_args__ = (
        Index(
            "uq_protocol_drafts_user_active",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'draft'"),
        ),
        Index("ix_protocol_drafts_user_status", "user_id", "status"),
        {"schema": __schema_name__},
    )


class ProtocolDraftItem(SchemaTableMixin, BaseModel):
    __tablename__ = "protocol_draft_items"
    __schema_name__ = "protocols"

    draft_id: Mapped[UUID] = mapped_column(
        ForeignKey("protocols.protocol_drafts.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("compound_catalog.compound_products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    selected_brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    selected_product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    draft: Mapped[ProtocolDraft] = relationship(back_populates="items")

    __table_args__ = (
        UniqueConstraint("draft_id", "product_id", name="uq_protocol_draft_item_product"),
        Index("ix_protocol_draft_items_draft_id", "draft_id"),
        {"schema": __schema_name__},
    )


class ProtocolDraftSettings(SchemaTableMixin, BaseModel):
    __tablename__ = "protocol_draft_settings"
    __schema_name__ = "protocols"

    draft_id: Mapped[UUID] = mapped_column(
        ForeignKey("protocols.protocol_drafts.id", ondelete="CASCADE"),
        nullable=False,
    )
    protocol_input_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    weekly_target_total_mg: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    duration_weeks: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    preset_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    max_injection_volume_ml: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    max_injections_per_week: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    planned_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    __table_args__ = (
        UniqueConstraint("draft_id", name="uq_protocol_draft_settings_draft_id"),
        Index("ix_protocol_draft_settings_draft_id", "draft_id"),
        {"schema": __schema_name__},
    )


class ProtocolInputTarget(SchemaTableMixin, BaseModel):
    __tablename__ = "protocol_input_targets"
    __schema_name__ = "protocols"

    draft_id: Mapped[UUID] = mapped_column(
        ForeignKey("protocols.protocol_drafts.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("compound_catalog.compound_products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    protocol_input_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    desired_weekly_mg: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "draft_id",
            "product_id",
            "protocol_input_mode",
            name="uq_protocol_input_target_identity",
        ),
        Index("ix_protocol_input_targets_draft_mode", "draft_id", "protocol_input_mode"),
        {"schema": __schema_name__},
    )


class ProtocolInventoryConstraint(SchemaTableMixin, BaseModel):
    __tablename__ = "protocol_inventory_constraints"
    __schema_name__ = "protocols"

    draft_id: Mapped[UUID] = mapped_column(
        ForeignKey("protocols.protocol_drafts.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("compound_catalog.compound_products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    protocol_input_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    available_count: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    count_unit: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "draft_id",
            "product_id",
            "protocol_input_mode",
            name="uq_protocol_inventory_constraint_identity",
        ),
        Index("ix_protocol_inventory_constraints_draft_mode", "draft_id", "protocol_input_mode"),
        {"schema": __schema_name__},
    )


class Protocol(SchemaTableMixin, BaseModel):
    __tablename__ = "protocols"
    __schema_name__ = "protocols"

    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    draft_id: Mapped[UUID] = mapped_column(
        ForeignKey("protocols.protocol_drafts.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_preview_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("pulse_engine.pulse_plan_previews.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="preview_ready")
    protocol_input_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    activated_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_by_protocol_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("protocols.protocols.id", ondelete="SET NULL"),
        nullable=True,
    )
    protocol_integrity_flagged_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    protocol_broken_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    settings_snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    summary_snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_protocols_user_status_created_at", "user_id", "status", "created_at"),
        Index("ix_protocols_draft_id_created_at", "draft_id", "created_at"),
        UniqueConstraint("source_preview_id", name="uq_protocols_source_preview_id"),
        {"schema": __schema_name__},
    )
