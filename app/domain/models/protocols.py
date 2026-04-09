from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Numeric, SmallInteger, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.db.base import BaseModel, SchemaTableMixin


class ProtocolDraft(SchemaTableMixin, BaseModel):
    __tablename__ = "protocol_drafts"
    __schema_name__ = "protocols"

    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")

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
            postgresql_where=text("status = 'active'"),
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
