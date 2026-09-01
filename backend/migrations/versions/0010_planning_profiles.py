"""Create minimal, soft-deletable planning profiles.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "planning_profiles",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("height_cm", sa.Numeric(precision=6, scale=2), nullable=False), sa.Column("weight_kg", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("age_years", sa.Integer(), nullable=False), sa.Column("formula_variant", sa.String(length=48), nullable=False),
        sa.Column("activity_level", sa.String(length=24), nullable=False), sa.Column("goal", sa.String(length=16), nullable=False),
        sa.Column("goal_speed", sa.String(length=24), nullable=False), sa.Column("target_policy_version", sa.String(length=80), nullable=False),
        sa.Column("formula_version", sa.String(length=80), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("height_cm >= 100 AND height_cm <= 250", name="ck_planning_profiles_height_range"),
        sa.CheckConstraint("weight_kg >= 20 AND weight_kg <= 350", name="ck_planning_profiles_weight_range"),
        sa.CheckConstraint("age_years >= 1 AND age_years <= 130", name="ck_planning_profiles_age_range"),
        sa.CheckConstraint("formula_variant IN ('mifflin_st_jeor_male', 'mifflin_st_jeor_female')", name="ck_planning_profiles_formula_variant"),
        sa.CheckConstraint("activity_level IN ('sedentary', 'light', 'moderate', 'high', 'very_high')", name="ck_planning_profiles_activity_level"),
        sa.CheckConstraint("goal IN ('maintain', 'loss', 'gain')", name="ck_planning_profiles_goal"),
        sa.CheckConstraint("goal_speed IN ('maintain', 'gradual_loss', 'gradual_gain')", name="ck_planning_profiles_goal_speed"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_planning_profiles_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_planning_profiles"),
    )
    op.create_index("uq_planning_profiles_active_user", "planning_profiles", ["user_id"], unique=True, postgresql_where=sa.text("deleted_at IS NULL"))


def downgrade() -> None:
    op.drop_index("uq_planning_profiles_active_user", table_name="planning_profiles")
    op.drop_table("planning_profiles")
