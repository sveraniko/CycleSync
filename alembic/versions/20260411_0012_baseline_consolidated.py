"""consolidated baseline schema

Revision ID: 20260411_0012
Revises: 
Create Date: 2026-04-11 03:00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260411_0012"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMAS: tuple[str, ...] = (
    "compound_catalog",
    "user_registry",
    "protocols",
    "pulse_engine",
    "reminders",
    "adherence",
    "labs",
    "ai_triage",
    "expert_cases",
    "search_read",
    "analytics_raw",
    "analytics_views",
    "ops",
    "access",
    "billing",
)


def upgrade() -> None:
    # from 20260409_0001_baseline_schemas_and_ops.py
    for schema in SCHEMAS:
        op.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))

    op.create_table(
        "entitlements",
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_access_entitlements"),
        sa.UniqueConstraint("code", name="uq_access_entitlements_code"),
        schema="access",
    )

    op.create_table(
        "entitlement_grants",
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("entitlement_code", sa.String(length=64), nullable=False),
        sa.Column("grant_status", sa.String(length=24), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("granted_by_source", sa.String(length=24), nullable=False),
        sa.Column("source_ref", sa.String(length=255), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("revoked_reason", sa.String(length=255), nullable=True),
        sa.Column("replaced_by_grant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["entitlement_code"], ["access.entitlements.code"], ondelete="RESTRICT", name="fk_access_grants_entitlement_code"),
        sa.PrimaryKeyConstraint("id", name="pk_access_entitlement_grants"),
        schema="access",
    )
    op.create_index(
        "ix_access_entitlement_grants_user_entitlement_status",
        "entitlement_grants",
        ["user_id", "entitlement_code", "grant_status"],
        unique=False,
        schema="access",
    )
    op.create_index(
        "ix_access_entitlement_grants_entitlement_status_expires",
        "entitlement_grants",
        ["entitlement_code", "grant_status", "expires_at"],
        unique=False,
        schema="access",
    )
    op.create_table(
        "access_keys",
        sa.Column("key_code", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("max_redemptions", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("redeemed_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_source", sa.String(length=64), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_access_access_keys"),
        sa.UniqueConstraint("key_code", name="uq_access_access_keys_key_code"),
        schema="access",
    )
    op.create_index(
        "ix_access_access_keys_status_expires",
        "access_keys",
        ["status", "expires_at"],
        unique=False,
        schema="access",
    )
    op.create_table(
        "access_key_entitlements",
        sa.Column("access_key_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entitlement_code", sa.String(length=64), nullable=False),
        sa.Column("grant_duration_days", sa.Integer(), nullable=True),
        sa.Column("grant_status_template", sa.String(length=24), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["access_key_id"], ["access.access_keys.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entitlement_code"], ["access.entitlements.code"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_access_access_key_entitlements"),
        sa.UniqueConstraint("access_key_id", "entitlement_code", name="uq_access_key_entitlement_identity"),
        schema="access",
    )
    op.create_table(
        "access_key_redemptions",
        sa.Column("access_key_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("result_status", sa.String(length=24), nullable=False),
        sa.Column("result_reason_code", sa.String(length=64), nullable=True),
        sa.Column("created_grant_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["access_key_id"], ["access.access_keys.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_access_access_key_redemptions"),
        schema="access",
    )
    op.create_index(
        "ix_access_access_key_redemptions_key_user",
        "access_key_redemptions",
        ["access_key_id", "user_id"],
        unique=False,
        schema="access",
    )
    op.create_index(
        "ix_access_access_key_redemptions_redeemed_at",
        "access_key_redemptions",
        ["redeemed_at"],
        unique=False,
        schema="access",
    )
    op.create_table(
        "checkouts",
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("checkout_status", sa.String(length=24), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("subtotal_amount", sa.Integer(), nullable=False),
        sa.Column("discount_amount", sa.Integer(), nullable=False),
        sa.Column("total_amount", sa.Integer(), nullable=False),
        sa.Column("settlement_mode", sa.String(length=24), nullable=False),
        sa.Column("source_context", sa.String(length=64), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_billing_checkouts"),
        schema="billing",
    )
    op.create_index(
        "ix_billing_checkouts_user_status",
        "checkouts",
        ["user_id", "checkout_status"],
        unique=False,
        schema="billing",
    )
    op.create_index(
        "ix_billing_checkouts_created_at",
        "checkouts",
        ["created_at"],
        unique=False,
        schema="billing",
    )
    op.create_table(
        "sellable_offers",
        sa.Column("offer_code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("default_amount", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_billing_sellable_offers"),
        sa.UniqueConstraint("offer_code", name="uq_billing_sellable_offers_offer_code"),
        schema="billing",
    )
    op.create_index(
        "ix_billing_sellable_offers_status",
        "sellable_offers",
        ["status"],
        unique=False,
        schema="billing",
    )
    op.create_index(
        "ix_billing_sellable_offers_code",
        "sellable_offers",
        ["offer_code"],
        unique=False,
        schema="billing",
    )
    op.create_table(
        "offer_entitlements",
        sa.Column("offer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entitlement_code", sa.String(length=64), nullable=False),
        sa.Column("grant_duration_days", sa.Integer(), nullable=True),
        sa.Column("qty", sa.Integer(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["offer_id"], ["billing.sellable_offers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entitlement_code"], ["access.entitlements.code"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_billing_offer_entitlements"),
        sa.UniqueConstraint("offer_id", "entitlement_code", name="uq_billing_offer_entitlements_offer_entitlement"),
        schema="billing",
    )
    op.create_index(
        "ix_billing_offer_entitlements_offer",
        "offer_entitlements",
        ["offer_id"],
        unique=False,
        schema="billing",
    )
    op.create_index(
        "ix_billing_offer_entitlements_offer_code",
        "offer_entitlements",
        ["offer_id", "entitlement_code"],
        unique=False,
        schema="billing",
    )
    op.create_table(
        "checkout_items",
        sa.Column("checkout_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("offer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("offer_code", sa.String(length=64), nullable=False),
        sa.Column("item_code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("unit_amount", sa.Integer(), nullable=False),
        sa.Column("line_total", sa.Integer(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["checkout_id"], ["billing.checkouts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["offer_id"], ["billing.sellable_offers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_billing_checkout_items"),
        schema="billing",
    )
    op.create_table(
        "checkout_fulfillments",
        sa.Column("checkout_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fulfillment_status", sa.String(length=24), nullable=False),
        sa.Column("fulfilled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["checkout_id"], ["billing.checkouts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_billing_checkout_fulfillments"),
        sa.UniqueConstraint("checkout_id", name="uq_billing_checkout_fulfillments_checkout_id"),
        schema="billing",
    )
    op.create_index(
        "ix_billing_checkout_fulfillments_checkout",
        "checkout_fulfillments",
        ["checkout_id"],
        unique=False,
        schema="billing",
    )
    op.create_table(
        "coupons",
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("discount_type", sa.String(length=24), nullable=False),
        sa.Column("discount_value", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_redemptions_total", sa.Integer(), nullable=True),
        sa.Column("max_redemptions_per_user", sa.Integer(), nullable=True),
        sa.Column("redeemed_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("grants_free_checkout", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_billing_coupons"),
        sa.UniqueConstraint("code", name="uq_billing_coupons_code"),
        schema="billing",
    )
    op.create_index(
        "ix_billing_coupons_status_valid_to",
        "coupons",
        ["status", "valid_to"],
        unique=False,
        schema="billing",
    )
    op.create_table(
        "coupon_redemptions",
        sa.Column("coupon_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("checkout_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("result_status", sa.String(length=24), nullable=False),
        sa.Column("result_reason_code", sa.String(length=64), nullable=True),
        sa.Column("discount_amount", sa.Integer(), nullable=False),
        sa.Column("final_total_after_discount", sa.Integer(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["checkout_id"], ["billing.checkouts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["coupon_id"], ["billing.coupons.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_billing_coupon_redemptions"),
        schema="billing",
    )
    op.create_index(
        "ix_billing_coupon_redemptions_coupon_user",
        "coupon_redemptions",
        ["coupon_id", "user_id"],
        unique=False,
        schema="billing",
    )
    op.create_index(
        "ix_billing_coupon_redemptions_checkout",
        "coupon_redemptions",
        ["checkout_id"],
        unique=False,
        schema="billing",
    )
    op.create_table(
        "payment_attempts",
        sa.Column("checkout_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_code", sa.String(length=64), nullable=False),
        sa.Column("attempt_status", sa.String(length=24), nullable=False),
        sa.Column("requested_amount", sa.Integer(), nullable=False),
        sa.Column("provider_reference", sa.String(length=255), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["checkout_id"], ["billing.checkouts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_billing_payment_attempts"),
        schema="billing",
    )
    op.create_index(
        "ix_billing_payment_attempts_checkout",
        "payment_attempts",
        ["checkout_id"],
        unique=False,
        schema="billing",
    )
    op.create_table(
        "payment_provider_sessions",
        sa.Column("checkout_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_code", sa.String(length=64), nullable=False),
        sa.Column("session_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("session_status", sa.String(length=24), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["checkout_id"], ["billing.checkouts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_billing_payment_provider_sessions"),
        schema="billing",
    )
    op.create_index(
        "ix_billing_provider_sessions_checkout",
        "payment_provider_sessions",
        ["checkout_id"],
        unique=False,
        schema="billing",
    )

    op.execute(
        sa.text(
            """
            INSERT INTO access.entitlements (id, code, display_name, description, is_active)
            VALUES
            (gen_random_uuid(), 'bot_access', 'Bot access', 'Core bot shell access', true),
            (gen_random_uuid(), 'calculation_access', 'Calculation access', 'Pulse calculation execution access', true),
            (gen_random_uuid(), 'active_protocol_access', 'Active protocol access', 'Protocol activation and active lifecycle access', true),
            (gen_random_uuid(), 'reminders_access', 'Reminders access', 'Reminder enablement, materialization and dispatch access', true),
            (gen_random_uuid(), 'adherence_access', 'Adherence access', 'Adherence analytics and actions access', true),
            (gen_random_uuid(), 'ai_triage_access', 'AI triage access', 'Labs AI triage runtime access', true),
            (gen_random_uuid(), 'expert_case_access', 'Expert case access', 'Specialist consultation case access', true)
            """
        )
    )
    op.execute(
        sa.text(
            """
            WITH offers AS (
                INSERT INTO billing.sellable_offers (id, offer_code, title, status, currency, default_amount, description)
                VALUES
                (gen_random_uuid(), 'triage_access', 'AI triage access', 'active', 'USD', 100, 'AI triage runtime access offer'),
                (gen_random_uuid(), 'expert_case_access', 'Specialist consult access', 'active', 'USD', 1500, 'Specialist case assembly access offer')
                RETURNING id, offer_code
            )
            INSERT INTO billing.offer_entitlements (id, offer_id, entitlement_code, grant_duration_days, qty)
            SELECT gen_random_uuid(), offers.id,
                CASE WHEN offers.offer_code = 'triage_access' THEN 'ai_triage_access' ELSE 'expert_case_access' END,
                CASE WHEN offers.offer_code = 'triage_access' THEN 30 ELSE NULL END,
                1
            FROM offers
            """
        )
    )
    
    op.create_table(
        "outbox_events",
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("aggregate_type", sa.String(), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("correlation_id", sa.String(), nullable=True),
        sa.Column("causation_id", sa.String(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ops_outbox_events"),
        schema="ops",
    )
    op.create_index(
        "ix_ops_outbox_events_status_next_attempt",
        "outbox_events",
        ["status", "next_attempt_at"],
        unique=False,
        schema="ops",
    )
    
    op.create_table(
        "job_runs",
        sa.Column("job_name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("details_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ops_job_runs"),
        schema="ops",
    )
    
    op.create_table(
        "projection_checkpoints",
        sa.Column("projection_name", sa.String(), nullable=False),
        sa.Column("checkpoint", sa.String(), nullable=False),
        sa.Column("checkpointed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_ops_projection_checkpoints"),
        sa.UniqueConstraint("projection_name", name="uq_ops_projection_checkpoints_projection_name"),
        schema="ops",
    )
    # from 20260409_0002_compound_catalog_foundation.py
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
    # from 20260409_0003_search_foundation.py
    op.create_table(
        "search_projection_state",
        sa.Column("projection_name", sa.String(length=128), nullable=False),
        sa.Column("checkpoint", sa.String(length=128), nullable=False),
        sa.Column("checkpointed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("indexed_documents_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_rebuild_kind", sa.String(length=32), nullable=False, server_default=sa.text("'incremental'")),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_search_read_search_projection_state"),
        sa.UniqueConstraint("projection_name", name="uq_search_projection_state_name"),
        schema="search_read",
    )
    
    op.create_table(
        "search_query_logs",
        sa.Column("raw_query", sa.String(length=512), nullable=False),
        sa.Column("normalized_query", sa.String(length=512), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default=sa.text("'text'")),
        sa.Column("user_id", sa.String(length=64), nullable=True),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("was_found", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_search_read_search_query_logs"),
        schema="search_read",
    )
    op.create_index(
        "ix_search_query_logs_created_at",
        "search_query_logs",
        ["created_at"],
        unique=False,
        schema="search_read",
    )
    op.create_index(
        "ix_search_query_logs_was_found_created_at",
        "search_query_logs",
        ["was_found", "created_at"],
        unique=False,
        schema="search_read",
    )
    # from 20260409_0004_protocol_draft_foundation.py
    op.create_table(
        "protocol_drafts",
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'active'")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_protocols_protocol_drafts"),
        schema="protocols",
    )
    op.create_index(
        "ix_protocol_drafts_user_status",
        "protocol_drafts",
        ["user_id", "status"],
        unique=False,
        schema="protocols",
    )
    op.create_index(
        "uq_protocol_drafts_user_active",
        "protocol_drafts",
        ["user_id"],
        unique=True,
        schema="protocols",
        postgresql_where=sa.text("status = 'active'"),
    )
    
    op.create_table(
        "protocol_draft_items",
        sa.Column("draft_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("selected_brand", sa.String(length=255), nullable=True),
        sa.Column("selected_product_name", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["draft_id"], ["protocols.protocol_drafts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["compound_catalog.compound_products.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_protocols_protocol_draft_items"),
        sa.UniqueConstraint("draft_id", "product_id", name="uq_protocol_draft_item_product"),
        schema="protocols",
    )
    op.create_index(
        "ix_protocol_draft_items_draft_id",
        "protocol_draft_items",
        ["draft_id"],
        unique=False,
        schema="protocols",
    )
    # from 20260409_0005_wave2_pr1_pulse_prep_foundation.py
    op.add_column(
        "compound_products",
        sa.Column("max_injection_volume_ml", sa.Numeric(precision=10, scale=3), nullable=True),
        schema="compound_catalog",
    )
    op.add_column(
        "compound_products",
        sa.Column("is_automatable", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        schema="compound_catalog",
    )
    op.add_column(
        "compound_products",
        sa.Column("pharmacology_notes", sa.Text(), nullable=True),
        schema="compound_catalog",
    )
    op.add_column(
        "compound_products",
        sa.Column("composition_basis_notes", sa.Text(), nullable=True),
        schema="compound_catalog",
    )
    
    op.add_column(
        "compound_ingredients",
        sa.Column("half_life_days", sa.Numeric(precision=8, scale=3), nullable=True),
        schema="compound_catalog",
    )
    op.add_column(
        "compound_ingredients",
        sa.Column("dose_guidance_min_mg_week", sa.Numeric(precision=12, scale=4), nullable=True),
        schema="compound_catalog",
    )
    op.add_column(
        "compound_ingredients",
        sa.Column("dose_guidance_max_mg_week", sa.Numeric(precision=12, scale=4), nullable=True),
        schema="compound_catalog",
    )
    op.add_column(
        "compound_ingredients",
        sa.Column("dose_guidance_typical_mg_week", sa.Numeric(precision=12, scale=4), nullable=True),
        schema="compound_catalog",
    )
    op.add_column(
        "compound_ingredients",
        sa.Column("is_pulse_driver", sa.Boolean(), nullable=True),
        schema="compound_catalog",
    )
    
    op.create_table(
        "protocol_draft_settings",
        sa.Column("draft_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("weekly_target_total_mg", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("duration_weeks", sa.SmallInteger(), nullable=True),
        sa.Column("preset_code", sa.String(length=32), nullable=True),
        sa.Column("max_injection_volume_ml", sa.Numeric(precision=10, scale=3), nullable=True),
        sa.Column("max_injections_per_week", sa.SmallInteger(), nullable=True),
        sa.Column("planned_start_date", sa.Date(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["draft_id"], ["protocols.protocol_drafts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_protocols_protocol_draft_settings"),
        sa.UniqueConstraint("draft_id", name="uq_protocol_draft_settings_draft_id"),
        schema="protocols",
    )
    op.create_index(
        "ix_protocol_draft_settings_draft_id",
        "protocol_draft_settings",
        ["draft_id"],
        unique=False,
        schema="protocols",
    )
    # from 20260409_0006_wave2_pr2_pulse_engine_preview.py
    op.execute("CREATE SCHEMA IF NOT EXISTS pulse_engine")
    
    op.create_table(
        "pulse_calculation_runs",
        sa.Column("draft_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("preset_requested", sa.String(length=32), nullable=False),
        sa.Column("preset_applied", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("degraded_fallback", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("settings_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary_metrics_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("warning_flags_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["draft_id"], ["protocols.protocol_drafts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_pulse_engine_pulse_calculation_runs"),
        schema="pulse_engine",
    )
    op.create_index(
        "ix_pulse_calculation_runs_draft_id_created_at",
        "pulse_calculation_runs",
        ["draft_id", "created_at"],
        unique=False,
        schema="pulse_engine",
    )
    op.create_index(
        "ix_pulse_calculation_runs_status",
        "pulse_calculation_runs",
        ["status"],
        unique=False,
        schema="pulse_engine",
    )
    
    op.create_table(
        "pulse_plan_previews",
        sa.Column("draft_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("calculation_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("preset_requested", sa.String(length=32), nullable=False),
        sa.Column("preset_applied", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("degraded_fallback", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("settings_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary_metrics_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("warning_flags_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["calculation_run_id"], ["pulse_engine.pulse_calculation_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["draft_id"], ["protocols.protocol_drafts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_pulse_engine_pulse_plan_previews"),
        schema="pulse_engine",
    )
    op.create_index(
        "ix_pulse_plan_previews_draft_id_created_at",
        "pulse_plan_previews",
        ["draft_id", "created_at"],
        unique=False,
        schema="pulse_engine",
    )
    op.create_index("ix_pulse_plan_previews_status", "pulse_plan_previews", ["status"], unique=False, schema="pulse_engine")
    
    op.create_table(
        "pulse_plan_preview_entries",
        sa.Column("preview_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day_offset", sa.Integer(), nullable=False),
        sa.Column("scheduled_day", sa.Date(), nullable=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ingredient_context", sa.Text(), nullable=True),
        sa.Column("volume_ml", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("computed_mg", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("injection_event_key", sa.String(length=64), nullable=False),
        sa.Column("sequence_no", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["preview_id"], ["pulse_engine.pulse_plan_previews.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["compound_catalog.compound_products.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_pulse_engine_pulse_plan_preview_entries"),
        schema="pulse_engine",
    )
    op.create_index(
        "ix_pulse_plan_preview_entries_preview_day",
        "pulse_plan_preview_entries",
        ["preview_id", "day_offset", "sequence_no"],
        unique=False,
        schema="pulse_engine",
    )
    op.create_index(
        "ix_pulse_plan_preview_entries_product_id",
        "pulse_plan_preview_entries",
        ["product_id"],
        unique=False,
        schema="pulse_engine",
    )
    # from 20260409_0007_wave2_pr3_protocol_activation_foundation.py
    op.execute("UPDATE protocols.protocol_drafts SET status = 'draft' WHERE status = 'active'")
    op.drop_index("uq_protocol_drafts_user_active", table_name="protocol_drafts", schema="protocols")
    op.create_index(
        "uq_protocol_drafts_user_active",
        "protocol_drafts",
        ["user_id"],
        unique=True,
        schema="protocols",
        postgresql_where=sa.text("status = 'draft'"),
    )
    
    op.add_column(
        "pulse_plan_previews",
        sa.Column("lifecycle_status", sa.String(length=32), nullable=False, server_default="preview_ready"),
        schema="pulse_engine",
    )
    op.add_column("pulse_plan_previews", sa.Column("superseded_at", sa.Date(), nullable=True), schema="pulse_engine")
    
    op.create_table(
        "protocols",
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("draft_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_preview_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="preview_ready"),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_by_protocol_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("settings_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["draft_id"], ["protocols.protocol_drafts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_preview_id"], ["pulse_engine.pulse_plan_previews.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["superseded_by_protocol_id"], ["protocols.protocols.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_protocols_protocols"),
        sa.UniqueConstraint("source_preview_id", name="uq_protocols_source_preview_id"),
        schema="protocols",
    )
    op.create_index(
        "ix_protocols_user_status_created_at",
        "protocols",
        ["user_id", "status", "created_at"],
        unique=False,
        schema="protocols",
    )
    op.create_index(
        "ix_protocols_draft_id_created_at",
        "protocols",
        ["draft_id", "created_at"],
        unique=False,
        schema="protocols",
    )
    
    op.create_table(
        "pulse_plans",
        sa.Column("protocol_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_preview_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("preset_requested", sa.String(length=32), nullable=False),
        sa.Column("preset_applied", sa.String(length=32), nullable=False),
        sa.Column("settings_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary_metrics_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("warning_flags_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["protocol_id"], ["protocols.protocols.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_preview_id"], ["pulse_engine.pulse_plan_previews.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_pulse_engine_pulse_plans"),
        sa.UniqueConstraint("protocol_id", name="uq_pulse_plans_protocol_id"),
        schema="pulse_engine",
    )
    op.create_index(
        "ix_pulse_plans_protocol_id_created_at",
        "pulse_plans",
        ["protocol_id", "created_at"],
        unique=False,
        schema="pulse_engine",
    )
    
    op.create_table(
        "pulse_plan_entries",
        sa.Column("pulse_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day_offset", sa.Integer(), nullable=False),
        sa.Column("scheduled_day", sa.Date(), nullable=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ingredient_context", sa.Text(), nullable=True),
        sa.Column("volume_ml", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("computed_mg", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("injection_event_key", sa.String(length=64), nullable=False),
        sa.Column("sequence_no", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["pulse_plan_id"], ["pulse_engine.pulse_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["compound_catalog.compound_products.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_pulse_engine_pulse_plan_entries"),
        schema="pulse_engine",
    )
    op.create_index(
        "ix_pulse_plan_entries_plan_day",
        "pulse_plan_entries",
        ["pulse_plan_id", "day_offset", "sequence_no"],
        unique=False,
        schema="pulse_engine",
    )
    
    op.create_table(
        "reminder_schedule_requests",
        sa.Column("protocol_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pulse_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="requested"),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["protocol_id"], ["protocols.protocols.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pulse_plan_id"], ["pulse_engine.pulse_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_reminders_reminder_schedule_requests"),
        schema="reminders",
    )
    op.create_index(
        "ix_reminder_schedule_requests_protocol_id_created_at",
        "reminder_schedule_requests",
        ["protocol_id", "created_at"],
        unique=False,
        schema="reminders",
    )
    op.create_index(
        "ix_reminder_schedule_requests_status_created_at",
        "reminder_schedule_requests",
        ["status", "created_at"],
        unique=False,
        schema="reminders",
    )
    # from 20260410_0008_wave3_pr1_pulse_allocation_core.py
    op.add_column("pulse_calculation_runs", sa.Column("allocation_mode", sa.String(length=48), nullable=True), schema="pulse_engine")
    op.add_column("pulse_calculation_runs", sa.Column("guidance_coverage_score", sa.Numeric(5, 2), nullable=True), schema="pulse_engine")
    op.add_column(
        "pulse_calculation_runs",
        sa.Column("calculation_quality_flags_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        schema="pulse_engine",
    )
    op.add_column("pulse_calculation_runs", sa.Column("allocation_details_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True), schema="pulse_engine")
    
    op.add_column("pulse_plan_previews", sa.Column("allocation_mode", sa.String(length=48), nullable=True), schema="pulse_engine")
    op.add_column("pulse_plan_previews", sa.Column("guidance_coverage_score", sa.Numeric(5, 2), nullable=True), schema="pulse_engine")
    op.add_column(
        "pulse_plan_previews",
        sa.Column("calculation_quality_flags_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        schema="pulse_engine",
    )
    op.add_column("pulse_plan_previews", sa.Column("allocation_details_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True), schema="pulse_engine")
    
    op.alter_column("pulse_calculation_runs", "calculation_quality_flags_json", server_default=None, schema="pulse_engine")
    op.alter_column("pulse_plan_previews", "calculation_quality_flags_json", server_default=None, schema="pulse_engine")
    # from 20260411_0009_wave4_pr1_reminder_materialization_foundation.py
    op.add_column(
        "reminder_schedule_requests",
        sa.Column("error_message", sa.String(length=255), nullable=True),
        schema="reminders",
    )
    
    op.create_table(
        "protocol_reminders",
        sa.Column("protocol_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pulse_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pulse_plan_entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column(
            "reminder_kind",
            sa.String(length=32),
            nullable=False,
            server_default="injection",
        ),
        sa.Column("scheduled_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduled_local_date", sa.Date(), nullable=False),
        sa.Column("scheduled_local_time", sa.Time(), nullable=False),
        sa.Column("timezone_name", sa.String(length=64), nullable=False),
        sa.Column(
            "status", sa.String(length=32), nullable=False, server_default="scheduled"
        ),
        sa.Column(
            "is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("injection_event_key", sa.String(length=64), nullable=False),
        sa.Column("day_offset", sa.Integer(), nullable=False),
        sa.Column(
            "payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["protocol_id"], ["protocols.protocols.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["pulse_plan_id"], ["pulse_engine.pulse_plans.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["pulse_plan_entry_id"],
            ["pulse_engine.pulse_plan_entries.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_reminders_protocol_reminders"),
        sa.UniqueConstraint(
            "pulse_plan_entry_id",
            "reminder_kind",
            name="uq_protocol_reminders_entry_kind",
        ),
        schema="reminders",
    )
    op.create_index(
        "ix_protocol_reminders_protocol_status_schedule",
        "protocol_reminders",
        ["protocol_id", "status", "scheduled_at_utc"],
        unique=False,
        schema="reminders",
    )
    op.create_index(
        "ix_protocol_reminders_user_schedule",
        "protocol_reminders",
        ["user_id", "scheduled_at_utc"],
        unique=False,
        schema="reminders",
    )
    
    op.create_table(
        "user_notification_settings",
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column(
            "reminders_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("preferred_reminder_time_local", sa.Time(), nullable=True),
        sa.Column("timezone_name", sa.String(length=64), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "id", name="pk_user_registry_user_notification_settings"
        ),
        sa.UniqueConstraint(
            "user_id", name="uq_user_registry_user_notification_settings_user_id"
        ),
        schema="user_registry",
    )
    
    op.alter_column(
        "protocol_reminders", "reminder_kind", server_default=None, schema="reminders"
    )
    op.alter_column(
        "protocol_reminders", "status", server_default=None, schema="reminders"
    )
    op.alter_column(
        "protocol_reminders", "is_enabled", server_default=None, schema="reminders"
    )
    op.alter_column(
        "user_notification_settings",
        "reminders_enabled",
        server_default=None,
        schema="user_registry",
    )
    # from 20260411_0010_wave4_pr2_reminder_runtime_execution.py
    op.add_column(
        "protocol_reminders",
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        schema="reminders",
    )
    op.add_column(
        "protocol_reminders",
        sa.Column(
            "delivery_attempt_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        schema="reminders",
    )
    op.add_column(
        "protocol_reminders",
        sa.Column("last_delivery_error", sa.String(length=255), nullable=True),
        schema="reminders",
    )
    op.add_column(
        "protocol_reminders",
        sa.Column("last_message_chat_id", sa.String(length=128), nullable=True),
        schema="reminders",
    )
    op.add_column(
        "protocol_reminders",
        sa.Column("last_message_id", sa.String(length=128), nullable=True),
        schema="reminders",
    )
    op.add_column(
        "protocol_reminders",
        sa.Column(
            "awaiting_action_until_utc", sa.DateTime(timezone=True), nullable=True
        ),
        schema="reminders",
    )
    op.add_column(
        "protocol_reminders",
        sa.Column("snoozed_until_utc", sa.DateTime(timezone=True), nullable=True),
        schema="reminders",
    )
    op.add_column(
        "protocol_reminders",
        sa.Column("acted_at", sa.DateTime(timezone=True), nullable=True),
        schema="reminders",
    )
    op.add_column(
        "protocol_reminders",
        sa.Column("action_code", sa.String(length=32), nullable=True),
        schema="reminders",
    )
    op.add_column(
        "protocol_reminders",
        sa.Column("clean_after_utc", sa.DateTime(timezone=True), nullable=True),
        schema="reminders",
    )
    op.create_index(
        "ix_protocol_reminders_status_snooze",
        "protocol_reminders",
        ["status", "snoozed_until_utc"],
        unique=False,
        schema="reminders",
    )
    
    op.create_table(
        "protocol_adherence_events",
        sa.Column("protocol_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pulse_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reminder_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("action_code", sa.String(length=32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["protocol_id"], ["protocols.protocols.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["pulse_plan_id"], ["pulse_engine.pulse_plans.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["reminder_id"], ["reminders.protocol_reminders.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_adherence_protocol_adherence_events"),
        schema="adherence",
    )
    op.create_index(
        "ix_protocol_adherence_events_protocol_occurred",
        "protocol_adherence_events",
        ["protocol_id", "occurred_at"],
        unique=False,
        schema="adherence",
    )
    op.create_index(
        "ix_protocol_adherence_events_user_occurred",
        "protocol_adherence_events",
        ["user_id", "occurred_at"],
        unique=False,
        schema="adherence",
    )
    
    op.alter_column(
        "protocol_reminders",
        "delivery_attempt_count",
        server_default=None,
        schema="reminders",
    )
    # from 20260411_0011_wave5_pr1_adherence_intelligence.py
    op.create_table(
        "protocol_adherence_summaries",
        sa.Column("protocol_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pulse_plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("completed_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("snoozed_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("expired_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_actionable_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("completion_rate", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("skip_rate", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("expiry_rate", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_action_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("integrity_state", sa.String(length=32), nullable=False, server_default="healthy"),
        sa.Column("integrity_reason_code", sa.String(length=64), nullable=True),
        sa.Column("broken_reason_code", sa.String(length=64), nullable=True),
        sa.Column(
            "integrity_detail_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["protocol_id"], ["protocols.protocols.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pulse_plan_id"], ["pulse_engine.pulse_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_adherence_protocol_adherence_summaries"),
        sa.UniqueConstraint("protocol_id", name="uq_protocol_adherence_summaries_protocol"),
        schema="adherence",
    )
    op.create_index(
        "ix_protocol_adherence_summaries_user_updated",
        "protocol_adherence_summaries",
        ["user_id", "updated_at"],
        unique=False,
        schema="adherence",
    )
    op.create_index(
        "ix_protocol_adherence_summaries_integrity_state_updated",
        "protocol_adherence_summaries",
        ["integrity_state", "updated_at"],
        unique=False,
        schema="adherence",
    )
    
    op.add_column(
        "protocols",
        sa.Column("protocol_integrity_flagged_at", sa.DateTime(timezone=True), nullable=True),
        schema="protocols",
    )
    op.add_column(
        "protocols",
        sa.Column("protocol_broken_at", sa.DateTime(timezone=True), nullable=True),
        schema="protocols",
    )
    
    for col in [
        "completed_count",
        "skipped_count",
        "snoozed_count",
        "expired_count",
        "total_actionable_count",
        "completion_rate",
        "skip_rate",
        "expiry_rate",
        "integrity_state",
        "integrity_detail_json",
    ]:
        op.alter_column("protocol_adherence_summaries", col, server_default=None, schema="adherence")


    # from 20260411_0013_wave6_pr1_labs_foundation.py
    op.create_table(
        "markers",
        sa.Column("marker_code", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("category_code", sa.String(length=64), nullable=False),
        sa.Column("default_unit", sa.String(length=32), nullable=False),
        sa.Column("accepted_units", postgresql.ARRAY(sa.String(length=32)), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_labs_markers"),
        sa.UniqueConstraint("marker_code", name="uq_labs_markers_marker_code"),
        schema="labs",
    )
    op.create_index("ix_labs_markers_category_active", "markers", ["category_code", "is_active"], unique=False, schema="labs")

    op.create_table(
        "marker_aliases",
        sa.Column("marker_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("alias_text", sa.String(length=128), nullable=False),
        sa.Column("normalized_alias", sa.String(length=128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["marker_id"], ["labs.markers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_labs_marker_aliases"),
        sa.UniqueConstraint("marker_id", "normalized_alias", name="uq_labs_marker_aliases_marker_alias"),
        schema="labs",
    )
    op.create_index("ix_labs_marker_aliases_normalized_alias", "marker_aliases", ["normalized_alias"], unique=False, schema="labs")

    op.create_table(
        "lab_panels",
        sa.Column("panel_code", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_labs_lab_panels"),
        sa.UniqueConstraint("panel_code", name="uq_labs_lab_panels_panel_code"),
        schema="labs",
    )
    op.create_index("ix_labs_lab_panels_active", "lab_panels", ["is_active"], unique=False, schema="labs")

    op.create_table(
        "lab_panel_markers",
        sa.Column("panel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("marker_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["panel_id"], ["labs.lab_panels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["marker_id"], ["labs.markers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_labs_lab_panel_markers"),
        sa.UniqueConstraint("panel_id", "marker_id", name="uq_labs_panel_markers_pair"),
        schema="labs",
    )
    op.create_index("ix_labs_lab_panel_markers_panel_order", "lab_panel_markers", ["panel_id", "sort_order"], unique=False, schema="labs")

    op.create_table(
        "lab_reports",
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("protocol_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("source_lab_name", sa.String(length=128), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["protocol_id"], ["protocols.protocols.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_labs_lab_reports"),
        schema="labs",
    )
    op.create_index("ix_labs_lab_reports_user_date", "lab_reports", ["user_id", "report_date"], unique=False, schema="labs")
    op.create_index("ix_labs_lab_reports_protocol_date", "lab_reports", ["protocol_id", "report_date"], unique=False, schema="labs")

    op.create_table(
        "lab_report_entries",
        sa.Column("lab_report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("marker_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entered_value", sa.String(length=64), nullable=False),
        sa.Column("numeric_value", sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("reference_min", sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column("reference_max", sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column("entered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["lab_report_id"], ["labs.lab_reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["marker_id"], ["labs.markers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_labs_lab_report_entries"),
        sa.UniqueConstraint("lab_report_id", "marker_id", name="uq_labs_report_entries_report_marker"),
        schema="labs",
    )
    op.create_index("ix_labs_lab_report_entries_report_entered", "lab_report_entries", ["lab_report_id", "entered_at"], unique=False, schema="labs")

    # from 20260412_0014_wave6_pr2_labs_ai_triage.py
    op.create_table(
        "lab_triage_runs",
        sa.Column("lab_report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("protocol_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("triage_status", sa.String(length=32), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("urgent_flag", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("raw_result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["lab_report_id"], ["labs.lab_reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["protocol_id"], ["protocols.protocols.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_ai_triage_lab_triage_runs"),
        schema="ai_triage",
    )
    op.create_index("ix_ai_triage_runs_report_created", "lab_triage_runs", ["lab_report_id", "created_at"], unique=False, schema="ai_triage")
    op.create_index("ix_ai_triage_runs_user_created", "lab_triage_runs", ["user_id", "created_at"], unique=False, schema="ai_triage")

    op.create_table(
        "lab_triage_flags",
        sa.Column("triage_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("marker_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("flag_code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("suggested_followup", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["marker_id"], ["labs.markers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["triage_run_id"], ["ai_triage.lab_triage_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_ai_triage_lab_triage_flags"),
        schema="ai_triage",
    )
    op.create_index("ix_ai_triage_flags_run_severity", "lab_triage_flags", ["triage_run_id", "severity"], unique=False, schema="ai_triage")

    # from 20260412_0015_wave7_pr1_specialist_case_assembly.py
    op.create_table(
        "specialist_cases",
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("protocol_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lab_report_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("triage_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("case_status", sa.String(length=32), nullable=False, server_default=sa.text("'opened'")),
        sa.Column("opened_reason_code", sa.String(length=64), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latest_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("latest_response_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assigned_specialist_id", sa.String(length=64), nullable=True),
        sa.Column("notes_from_user", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["protocol_id"], ["protocols.protocols.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["lab_report_id"], ["labs.lab_reports.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["triage_run_id"], ["ai_triage.lab_triage_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_expert_cases_specialist_cases"),
        schema="expert_cases",
    )
    op.create_index("ix_expert_cases_specialist_cases_user_opened", "specialist_cases", ["user_id", "opened_at"], unique=False, schema="expert_cases")
    op.create_index("ix_expert_cases_specialist_cases_status_opened", "specialist_cases", ["case_status", "opened_at"], unique=False, schema="expert_cases")
    op.create_index("ix_expert_cases_specialist_cases_report_opened", "specialist_cases", ["lab_report_id", "opened_at"], unique=False, schema="expert_cases")

    op.create_table(
        "specialist_case_snapshots",
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_version", sa.Integer(), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["expert_cases.specialist_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_expert_cases_specialist_case_snapshots"),
        sa.UniqueConstraint("case_id", "snapshot_version", name="uq_specialist_case_snapshot_version"),
        schema="expert_cases",
    )
    op.create_index("ix_expert_cases_case_snapshots_case_version", "specialist_case_snapshots", ["case_id", "snapshot_version"], unique=False, schema="expert_cases")

    op.create_table(
        "specialist_case_responses",
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("responded_by", sa.String(length=64), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=False),
        sa.Column("response_summary", sa.Text(), nullable=True),
        sa.Column("is_final", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["expert_cases.specialist_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_expert_cases_specialist_case_responses"),
        schema="expert_cases",
    )
    op.create_index(
        "ix_expert_cases_case_responses_case_created",
        "specialist_case_responses",
        ["case_id", "created_at"],
        unique=False,
        schema="expert_cases",
    )
    op.create_foreign_key(
        "fk_expert_cases_specialist_cases_latest_snapshot",
        source_table="specialist_cases",
        referent_table="specialist_case_snapshots",
        local_cols=["latest_snapshot_id"],
        remote_cols=["id"],
        source_schema="expert_cases",
        referent_schema="expert_cases",
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_expert_cases_specialist_cases_latest_response",
        source_table="specialist_cases",
        referent_table="specialist_case_responses",
        local_cols=["latest_response_id"],
        remote_cols=["id"],
        source_schema="expert_cases",
        referent_schema="expert_cases",
        ondelete="SET NULL",
    )

    op.execute(sa.text("""
        INSERT INTO labs.markers (id, marker_code, display_name, category_code, default_unit, accepted_units, notes, is_active)
        VALUES
        (gen_random_uuid(), 'testosterone_total', 'Total Testosterone', 'male_hormones', 'ng/dL', ARRAY['ng/dL','nmol/L'], NULL, true),
        (gen_random_uuid(), 'testosterone_free', 'Free Testosterone', 'male_hormones', 'pg/mL', ARRAY['pg/mL','ng/dL'], NULL, true),
        (gen_random_uuid(), 'shbg', 'SHBG', 'male_hormones', 'nmol/L', ARRAY['nmol/L'], NULL, true),
        (gen_random_uuid(), 'lh', 'LH', 'male_hormones', 'mIU/mL', ARRAY['mIU/mL','IU/L'], NULL, true),
        (gen_random_uuid(), 'fsh', 'FSH', 'male_hormones', 'mIU/mL', ARRAY['mIU/mL','IU/L'], NULL, true),
        (gen_random_uuid(), 'prolactin', 'Prolactin', 'male_hormones', 'ng/mL', ARRAY['ng/mL','mIU/L'], NULL, true),
        (gen_random_uuid(), 'estradiol', 'Estradiol', 'male_hormones', 'pg/mL', ARRAY['pg/mL','pmol/L'], NULL, true),
        (gen_random_uuid(), 'dhea_s', 'DHEA-S', 'male_hormones', 'ug/dL', ARRAY['ug/dL','umol/L'], NULL, true),
        (gen_random_uuid(), 'hematocrit', 'Hematocrit', 'hematology', '%', ARRAY['%'], NULL, true),
        (gen_random_uuid(), 'hemoglobin', 'Hemoglobin', 'hematology', 'g/dL', ARRAY['g/dL','g/L'], NULL, true),
        (gen_random_uuid(), 'rbc', 'RBC', 'hematology', 'x10^12/L', ARRAY['x10^12/L'], NULL, true),
        (gen_random_uuid(), 'cholesterol_total', 'Total Cholesterol', 'lipids', 'mg/dL', ARRAY['mg/dL','mmol/L'], NULL, true),
        (gen_random_uuid(), 'cholesterol_ldl', 'LDL Cholesterol', 'lipids', 'mg/dL', ARRAY['mg/dL','mmol/L'], NULL, true),
        (gen_random_uuid(), 'cholesterol_hdl', 'HDL Cholesterol', 'lipids', 'mg/dL', ARRAY['mg/dL','mmol/L'], NULL, true),
        (gen_random_uuid(), 'triglycerides', 'Triglycerides', 'lipids', 'mg/dL', ARRAY['mg/dL','mmol/L'], NULL, true),
        (gen_random_uuid(), 'alt', 'ALT', 'liver', 'U/L', ARRAY['U/L'], NULL, true),
        (gen_random_uuid(), 'ast', 'AST', 'liver', 'U/L', ARRAY['U/L'], NULL, true),
        (gen_random_uuid(), 'ggt', 'GGT', 'liver', 'U/L', ARRAY['U/L'], NULL, true),
        (gen_random_uuid(), 'glucose_fasting', 'Fasting Glucose', 'metabolic', 'mg/dL', ARRAY['mg/dL','mmol/L'], NULL, true),
        (gen_random_uuid(), 'hba1c', 'HbA1c', 'metabolic', '%', ARRAY['%'], NULL, true),
        (gen_random_uuid(), 'igf_1', 'IGF-1', 'gh_related', 'ng/mL', ARRAY['ng/mL','nmol/L'], NULL, true)
    """))

    op.execute(sa.text("""
        INSERT INTO labs.lab_panels (id, panel_code, display_name, notes, is_active)
        VALUES
        (gen_random_uuid(), 'male_hormones', 'Male Hormones', NULL, true),
        (gen_random_uuid(), 'hematology', 'Hematology / Blood Thickness', NULL, true),
        (gen_random_uuid(), 'lipids', 'Lipids', NULL, true),
        (gen_random_uuid(), 'liver', 'Liver', NULL, true),
        (gen_random_uuid(), 'metabolic', 'Metabolic', NULL, true),
        (gen_random_uuid(), 'gh_related', 'GH-related', NULL, true)
    """))

    op.execute(sa.text("""
        INSERT INTO labs.lab_panel_markers (id, panel_id, marker_id, sort_order, is_required)
        SELECT gen_random_uuid(), p.id, m.id, row_number() OVER (PARTITION BY p.id ORDER BY m.display_name), false
        FROM labs.lab_panels p
        JOIN labs.markers m ON (
            (p.panel_code = 'male_hormones' AND m.category_code = 'male_hormones') OR
            (p.panel_code = 'hematology' AND m.category_code = 'hematology') OR
            (p.panel_code = 'lipids' AND m.category_code = 'lipids') OR
            (p.panel_code = 'liver' AND m.category_code = 'liver') OR
            (p.panel_code = 'metabolic' AND m.category_code = 'metabolic') OR
            (p.panel_code = 'gh_related' AND (m.category_code = 'gh_related' OR m.marker_code = 'glucose_fasting'))
        )
    """))


def downgrade() -> None:
    raise NotImplementedError("Baseline downgrade is intentionally unsupported in pre-release consolidation.")
