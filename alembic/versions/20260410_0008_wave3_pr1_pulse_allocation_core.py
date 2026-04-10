"""wave3 pr1 pulse allocation core

Revision ID: 20260410_0008
Revises: 20260409_0007
Create Date: 2026-04-10 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260410_0008"
down_revision = "20260409_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_column("pulse_plan_previews", "allocation_details_json", schema="pulse_engine")
    op.drop_column("pulse_plan_previews", "calculation_quality_flags_json", schema="pulse_engine")
    op.drop_column("pulse_plan_previews", "guidance_coverage_score", schema="pulse_engine")
    op.drop_column("pulse_plan_previews", "allocation_mode", schema="pulse_engine")

    op.drop_column("pulse_calculation_runs", "allocation_details_json", schema="pulse_engine")
    op.drop_column("pulse_calculation_runs", "calculation_quality_flags_json", schema="pulse_engine")
    op.drop_column("pulse_calculation_runs", "guidance_coverage_score", schema="pulse_engine")
    op.drop_column("pulse_calculation_runs", "allocation_mode", schema="pulse_engine")
