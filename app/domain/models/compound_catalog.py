from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.db.base import BaseModel, SchemaTableMixin


class Brand(SchemaTableMixin, BaseModel):
    __tablename__ = "brands"
    __schema_name__ = "compound_catalog"

    product_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="google_sheets")
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    products: Mapped[list["CompoundProduct"]] = relationship(back_populates="brand")

    __table_args__ = (
        UniqueConstraint("normalized_name", name="uq_catalog_brands_normalized_name"),
        Index("ix_catalog_brands_is_active", "is_active"),
        {"schema": __schema_name__},
    )


class CompoundProduct(SchemaTableMixin, BaseModel):
    __tablename__ = "compound_products"
    __schema_name__ = "compound_catalog"

    brand_id: Mapped[UUID] = mapped_column(
        ForeignKey("compound_catalog.brands.id", ondelete="RESTRICT"), nullable=False
    )
    product_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    trade_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_trade_name: Mapped[str] = mapped_column(String(255), nullable=False)
    release_form: Mapped[str | None] = mapped_column(String(128), nullable=True)
    concentration_raw: Mapped[str | None] = mapped_column(String(128), nullable=True)
    concentration_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    concentration_unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    concentration_basis: Mapped[str | None] = mapped_column(String(32), nullable=True)
    package_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    units_per_package: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    volume_per_package_ml: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    unit_strength_mg: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    official_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    authenticity_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_injection_volume_ml: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    is_automatable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    pharmacology_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    composition_basis_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="google_sheets")
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    brand: Mapped[Brand] = relationship(back_populates="products")
    aliases: Mapped[list["CompoundAlias"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    ingredients: Mapped[list["CompoundIngredient"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    media_refs: Mapped[list["ProductMediaRef"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    source_refs: Mapped[list["ProductSourceRef"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint(
            "brand_id",
            "normalized_trade_name",
            "release_form",
            "concentration_raw",
            name="uq_catalog_product_identity",
        ),
        UniqueConstraint("product_key", name="uq_catalog_product_key"),
        UniqueConstraint("source", "source_ref", name="uq_catalog_product_source_ref"),
        Index("ix_catalog_compound_products_is_active", "is_active"),
        Index("ix_catalog_compound_products_brand_id", "brand_id"),
        Index("ix_catalog_compound_products_normalized_display_name", "normalized_display_name"),
        {"schema": __schema_name__},
    )


class CompoundAlias(SchemaTableMixin, BaseModel):
    __tablename__ = "compound_aliases"
    __schema_name__ = "compound_catalog"

    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("compound_catalog.compound_products.id", ondelete="CASCADE"), nullable=False
    )
    alias_text: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    product: Mapped[CompoundProduct] = relationship(back_populates="aliases")

    __table_args__ = (
        UniqueConstraint("product_id", "normalized_alias", name="uq_catalog_alias_product_norm"),
        Index("ix_catalog_compound_aliases_normalized_alias", "normalized_alias"),
        {"schema": __schema_name__},
    )


class CompoundIngredient(SchemaTableMixin, BaseModel):
    __tablename__ = "compound_ingredients"
    __schema_name__ = "compound_catalog"

    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("compound_catalog.compound_products.id", ondelete="CASCADE"), nullable=False
    )
    parent_substance: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ingredient_name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_ingredient_name: Mapped[str] = mapped_column(String(255), nullable=False)
    ester_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    qualifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    basis: Mapped[str | None] = mapped_column(String(32), nullable=True)
    amount_per_ml_mg: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    amount_per_unit_mg: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    half_life_days: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    active_fraction: Mapped[Decimal | None] = mapped_column(Numeric(8, 5), nullable=True)
    tmax_hours: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    release_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pk_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    dose_guidance_min_mg_week: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    dose_guidance_max_mg_week: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    dose_guidance_typical_mg_week: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    is_pulse_driver: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    product: Mapped[CompoundProduct] = relationship(back_populates="ingredients")

    __table_args__ = (
        UniqueConstraint(
            "product_id",
            "normalized_ingredient_name",
            "ester_name",
            "qualifier",
            "amount",
            "unit",
            "basis",
            name="uq_catalog_ingredient_identity",
        ),
        Index("ix_catalog_compound_ingredients_product_id", "product_id"),
        Index("ix_catalog_compound_ingredients_normalized_name", "normalized_ingredient_name"),
        {"schema": __schema_name__},
    )


class ProductMediaRef(SchemaTableMixin, BaseModel):
    __tablename__ = "product_media_refs"
    __schema_name__ = "compound_catalog"

    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("compound_catalog.compound_products.id", ondelete="CASCADE"), nullable=False
    )
    media_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    ref_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_cover: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_layer: Mapped[str] = mapped_column(String(16), nullable=False, default="import")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    product: Mapped[CompoundProduct] = relationship(back_populates="media_refs")

    __table_args__ = (
        UniqueConstraint("product_id", "media_kind", "ref_url", name="uq_catalog_media_identity"),
        Index("ix_catalog_product_media_refs_product_id", "product_id"),
        {"schema": __schema_name__},
    )


class ProductSourceRef(SchemaTableMixin, BaseModel):
    __tablename__ = "product_source_refs"
    __schema_name__ = "compound_catalog"

    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("compound_catalog.compound_products.id", ondelete="CASCADE"), nullable=False
    )
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="source")
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_layer: Mapped[str] = mapped_column(String(16), nullable=False, default="import")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    product: Mapped[CompoundProduct] = relationship(back_populates="source_refs")

    __table_args__ = (
        UniqueConstraint("product_id", "source_kind", "url", "source_layer", name="uq_catalog_source_ref_identity"),
        Index("ix_catalog_product_source_refs_product_id", "product_id"),
        {"schema": __schema_name__},
    )


class CatalogIngestRun(SchemaTableMixin, BaseModel):
    __tablename__ = "catalog_ingest_runs"
    __schema_name__ = "compound_catalog"

    source_name: Mapped[str] = mapped_column(String(64), nullable=False)
    source_sheet_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_tab: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    issue_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    details_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    source_records: Mapped[list["CatalogSourceRecord"]] = relationship(back_populates="ingest_run")

    __table_args__ = (
        Index("ix_catalog_ingest_runs_status_started", "status", "started_at"),
        {"schema": __schema_name__},
    )


class CatalogSourceRecord(SchemaTableMixin, BaseModel):
    __tablename__ = "catalog_source_records"
    __schema_name__ = "compound_catalog"

    ingest_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("compound_catalog.catalog_ingest_runs.id", ondelete="CASCADE"), nullable=False
    )
    source_row_key: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    issue_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("compound_catalog.compound_products.id", ondelete="SET NULL"),
        nullable=True,
    )

    ingest_run: Mapped[CatalogIngestRun] = relationship(back_populates="source_records")

    __table_args__ = (
        UniqueConstraint(
            "ingest_run_id",
            "source_row_key",
            name="uq_catalog_source_record_ingest_row",
        ),
        Index("ix_catalog_source_records_status", "status"),
        {"schema": __schema_name__},
    )
