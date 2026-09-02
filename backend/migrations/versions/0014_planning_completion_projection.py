"""Persist revocable, owner-bound validated-planning dashboard eligibility.

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-02

Phase 5 owns 0011/0012 and Phase 06-01 owns 0013. This migration deliberately
continues the single linear chain instead of recreating the obsolete 0012 revision.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("planning_profiles", sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
    op.create_unique_constraint("uq_planning_profiles_user_id", "planning_profiles", ["user_id", "id"])
    op.create_unique_constraint("uq_agent_threads_user_id", "agent_threads", ["user_id", "id"])
    op.create_unique_constraint("uq_agent_runs_user_thread_id", "agent_runs", ["user_id", "thread_id", "id"])
    op.create_table(
        "planning_completion_projections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("completed_thread_id", sa.Uuid(), nullable=False),
        sa.Column("completed_run_id", sa.Uuid(), nullable=False),
        sa.Column("profile_revision", sa.Integer(), nullable=False),
        sa.Column("target_version", sa.String(length=80), nullable=False),
        sa.Column("energy_kcal_lower", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("energy_kcal_upper", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("carbohydrate_g_lower", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("carbohydrate_g_upper", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("protein_g_lower", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("protein_g_upper", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("fat_g_lower", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("fat_g_upper", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.String(length=48), nullable=True),
        sa.CheckConstraint("profile_revision >= 1", name="ck_planning_completion_projections_profile_revision"),
        sa.CheckConstraint("target_version = btrim(target_version) AND target_version <> ''", name="ck_planning_completion_projections_target_version"),
        sa.CheckConstraint("energy_kcal_lower >= 0 AND energy_kcal_upper >= energy_kcal_lower AND carbohydrate_g_lower >= 0 AND carbohydrate_g_upper >= carbohydrate_g_lower AND protein_g_lower >= 0 AND protein_g_upper >= protein_g_lower AND fat_g_lower >= 0 AND fat_g_upper >= fat_g_lower", name="ck_planning_completion_projections_target_ranges"),
        sa.CheckConstraint("(revoked_at IS NULL AND revocation_reason IS NULL) OR (revoked_at IS NOT NULL AND revocation_reason IN ('profile_revision_changed', 'profile_deleted'))", name="ck_planning_completion_projections_revocation"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_planning_completion_projections_user", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id", "profile_id"], ["planning_profiles.user_id", "planning_profiles.id"], name="fk_planning_completion_projections_profile", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id", "completed_thread_id"], ["agent_threads.user_id", "agent_threads.id"], name="fk_planning_completion_projections_thread", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id", "completed_thread_id", "completed_run_id"], ["agent_runs.user_id", "agent_runs.thread_id", "agent_runs.id"], name="fk_planning_completion_projections_run", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_planning_completion_projections"),
        sa.UniqueConstraint("user_id", "completed_run_id", name="uq_planning_completion_projections_user_run"),
    )
    op.create_index("ix_planning_completion_projections_user_active", "planning_completion_projections", ["user_id", "completed_at", "id"], postgresql_where=sa.text("revoked_at IS NULL"))
    op.alter_column("planning_profiles", "revision", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_planning_completion_projections_user_active", table_name="planning_completion_projections")
    op.drop_table("planning_completion_projections")
    op.drop_constraint("uq_agent_runs_user_thread_id", "agent_runs", type_="unique")
    op.drop_constraint("uq_agent_threads_user_id", "agent_threads", type_="unique")
    op.drop_constraint("uq_planning_profiles_user_id", "planning_profiles", type_="unique")
    op.drop_column("planning_profiles", "revision")
