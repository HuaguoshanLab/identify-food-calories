"""Freeze meal-record local-date attribution from explicit IANA timezone facts.

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-02

Phase 5 already owns revisions 0011 and 0012, so this is the first available
linear successor for Phase 6 rather than creating a parallel migration head.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("meal_records", sa.Column("consumed_time_zone", sa.String(length=64), nullable=True))
    op.add_column("meal_records", sa.Column("consumed_local_date", sa.Date(), nullable=True))
    op.add_column("meal_records", sa.Column("local_date_source", sa.String(length=48), nullable=True))
    op.create_check_constraint(
        "ck_meal_records_local_date_attribution",
        "meal_records",
        "(consumed_time_zone IS NULL AND consumed_local_date IS NULL AND local_date_source IS NULL) "
        "OR (consumed_time_zone IS NOT NULL AND consumed_local_date IS NOT NULL "
        "AND local_date_source IN ('submitted_time_zone', 'confirmed_timezone_backfill'))",
    )
    op.create_index(
        "ix_meal_records_user_local_date_active", "meal_records", ["user_id", "consumed_local_date", "id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "dashboard_timezone_preferences",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("time_zone", sa.String(length=64), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_dashboard_timezone_preferences_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", name="pk_dashboard_timezone_preferences"),
    )
    op.create_table(
        "dashboard_timezone_backfill_audits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("confirmed_time_zone", sa.String(length=64), nullable=False),
        sa.Column("records_backfilled", sa.Integer(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("records_backfilled >= 0", name="ck_dashboard_timezone_backfill_audits_count"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_dashboard_timezone_backfill_audits_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_dashboard_timezone_backfill_audits"),
        sa.UniqueConstraint("user_id", name="uq_dashboard_timezone_backfill_audits_user"),
    )


def downgrade() -> None:
    op.drop_table("dashboard_timezone_backfill_audits")
    op.drop_table("dashboard_timezone_preferences")
    op.drop_index("ix_meal_records_user_local_date_active", table_name="meal_records")
    op.drop_constraint("ck_meal_records_local_date_attribution", "meal_records", type_="check")
    op.drop_column("meal_records", "local_date_source")
    op.drop_column("meal_records", "consumed_local_date")
    op.drop_column("meal_records", "consumed_time_zone")
