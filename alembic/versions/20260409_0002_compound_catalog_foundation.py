"""compound catalog transactional foundation

Revision ID: 20260409_0002
Revises: 20260409_0001
Create Date: 2026-04-09 01:00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260409_0002"
down_revision: Union[str, Sequence[str], None] = "20260409_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "brands",
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_compound_catalog_brands"),
        sa.UniqueConstraint("normalized_name", name="uq_catalog_brands_normalized_name"),
        schema="compound_catalog",
    )
    op.create_index(
        "ix_catalog_brands_is_active",
        "brands",
        ["is_active"],
        unique=False,
        schema="compound_catalog",
    )

    op.create_table(
        "compound_products",
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("normalized_display_name", sa.String(length=255), nullable=False),
        sa.Column("trade_name", sa.String(length=255), nullable=False),
        sa.Column("normalized_trade_name", sa.String(length=255), nullable=False),
        sa.Column("release_form", sa.String(length=128), nullable=True),
        sa.Column("concentration_raw", sa.String(length=128), nullable=True),
        sa.Column("concentration_value", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("concentration_unit", sa.String(length=32), nullable=True),
        sa.Column("concentration_basis", sa.String(length=32), nullable=True),
        sa.Column("official_url", sa.String(length=1024), nullable=True),
        sa.Column("authenticity_notes", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_ref", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["compound_catalog.brands.id"], ondelete="RESTRICT", name="fk_catalog_product_brand"),
        sa.PrimaryKeyConstraint("id", name="pk_compound_catalog_compound_products"),
        sa.UniqueConstraint(
            "brand_id",
            "normalized_trade_name",
            "release_form",
            "concentration_raw",
            name="uq_catalog_product_identity",
        ),
        sa.UniqueConstraint("source", "source_ref", name="uq_catalog_product_source_ref"),
        schema="compound_catalog",
    )
    op.create_index(
        "ix_catalog_compound_products_is_active",
        "compound_products",
        ["is_active"],
        unique=False,
        schema="compound_catalog",
    )
    op.create_index(
        "ix_catalog_compound_products_brand_id",
        "compound_products",
        ["brand_id"],
        unique=False,
        schema="compound_catalog",
    )
    op.create_index(
        "ix_catalog_compound_products_normalized_display_name",
        "compound_products",
        ["normalized_display_name"],
        unique=False,
        schema="compound_catalog",
    )

    op.create_table(
        "compound_aliases",
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("alias_text", sa.String(length=255), nullable=False),
        sa.Column("normalized_alias", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["compound_catalog.compound_products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_compound_catalog_compound_aliases"),
        sa.UniqueConstraint("product_id", "normalized_alias", name="uq_catalog_alias_product_norm"),
        schema="compound_catalog",
    )
    op.create_index(
        "ix_catalog_compound_aliases_normalized_alias",
        "compound_aliases",
        ["normalized_alias"],
        unique=False,
        schema="compound_catalog",
    )

    op.create_table(
        "compound_ingredients",
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ingredient_name", sa.String(length=255), nullable=False),
        sa.Column("normalized_ingredient_name", sa.String(length=255), nullable=False),
        sa.Column("qualifier", sa.String(length=255), nullable=True),
        sa.Column("amount", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("basis", sa.String(length=32), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["compound_catalog.compound_products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_compound_catalog_compound_ingredients"),
        sa.UniqueConstraint(
            "product_id",
            "normalized_ingredient_name",
            "qualifier",
            "amount",
            "unit",
            "basis",
            name="uq_catalog_ingredient_identity",
        ),
        schema="compound_catalog",
    )
    op.create_index(
        "ix_catalog_compound_ingredients_product_id",
        "compound_ingredients",
        ["product_id"],
        unique=False,
        schema="compound_catalog",
    )
    op.create_index(
        "ix_catalog_compound_ingredients_normalized_name",
        "compound_ingredients",
        ["normalized_ingredient_name"],
        unique=False,
        schema="compound_catalog",
    )

    op.create_table(
        "product_media_refs",
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("media_kind", sa.String(length=16), nullable=False),
        sa.Column("ref_url", sa.String(length=1024), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["compound_catalog.compound_products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_compound_catalog_product_media_refs"),
        sa.UniqueConstraint("product_id", "media_kind", "ref_url", name="uq_catalog_media_identity"),
        schema="compound_catalog",
    )
    op.create_index(
        "ix_catalog_product_media_refs_product_id",
        "product_media_refs",
        ["product_id"],
        unique=False,
        schema="compound_catalog",
    )

    op.create_table(
        "catalog_ingest_runs",
        sa.Column("source_name", sa.String(length=64), nullable=False),
        sa.Column("source_sheet_id", sa.String(length=255), nullable=True),
        sa.Column("source_tab", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("processed_rows", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("issue_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("details_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_compound_catalog_catalog_ingest_runs"),
        schema="compound_catalog",
    )
    op.create_index(
        "ix_catalog_ingest_runs_status_started",
        "catalog_ingest_runs",
        ["status", "started_at"],
        unique=False,
        schema="compound_catalog",
    )

    op.create_table(
        "catalog_source_records",
        sa.Column("ingest_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_row_key", sa.String(length=255), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("issue_text", sa.Text(), nullable=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ingest_run_id"], ["compound_catalog.catalog_ingest_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["compound_catalog.compound_products.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_compound_catalog_catalog_source_records"),
        sa.UniqueConstraint("ingest_run_id", "source_row_key", name="uq_catalog_source_record_ingest_row"),
        schema="compound_catalog",
    )
    op.create_index(
        "ix_catalog_source_records_status",
        "catalog_source_records",
        ["status"],
        unique=False,
        schema="compound_catalog",
    )


def downgrade() -> None:
    op.drop_index("ix_catalog_source_records_status", table_name="catalog_source_records", schema="compound_catalog")
    op.drop_table("catalog_source_records", schema="compound_catalog")

    op.drop_index("ix_catalog_ingest_runs_status_started", table_name="catalog_ingest_runs", schema="compound_catalog")
    op.drop_table("catalog_ingest_runs", schema="compound_catalog")

    op.drop_index("ix_catalog_product_media_refs_product_id", table_name="product_media_refs", schema="compound_catalog")
    op.drop_table("product_media_refs", schema="compound_catalog")

    op.drop_index("ix_catalog_compound_ingredients_normalized_name", table_name="compound_ingredients", schema="compound_catalog")
    op.drop_index("ix_catalog_compound_ingredients_product_id", table_name="compound_ingredients", schema="compound_catalog")
    op.drop_table("compound_ingredients", schema="compound_catalog")

    op.drop_index("ix_catalog_compound_aliases_normalized_alias", table_name="compound_aliases", schema="compound_catalog")
    op.drop_table("compound_aliases", schema="compound_catalog")

    op.drop_index("ix_catalog_compound_products_normalized_display_name", table_name="compound_products", schema="compound_catalog")
    op.drop_index("ix_catalog_compound_products_brand_id", table_name="compound_products", schema="compound_catalog")
    op.drop_index("ix_catalog_compound_products_is_active", table_name="compound_products", schema="compound_catalog")
    op.drop_table("compound_products", schema="compound_catalog")

    op.drop_index("ix_catalog_brands_is_active", table_name="brands", schema="compound_catalog")
    op.drop_table("brands", schema="compound_catalog")
