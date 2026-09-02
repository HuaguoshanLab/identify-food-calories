"""Persist minimal, versioned weekly-review cache results.

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-02

Phase 06 originally reserved 0013 for this change, but dashboard time attribution
and planning completion already own 0013 and 0014.  Keep this migration on 0015
to preserve the sole Alembic head; subsequent Phase 06 revisions continue at 0016.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "weekly_review_results",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("user_id", sa.Uuid(), nullable=False), sa.Column("week_start", sa.Date(), nullable=False), sa.Column("facts_digest", sa.String(length=64), nullable=False),
        sa.Column("graph_version", sa.String(length=80), nullable=False), sa.Column("prompt_version", sa.String(length=80), nullable=False), sa.Column("schema_version", sa.String(length=80), nullable=False), sa.Column("runtime_config_version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False), sa.Column("advice", sa.String(length=500), nullable=True), sa.Column("abstention_code", sa.String(length=80), nullable=True), sa.Column("result_digest", sa.String(length=64), nullable=False), sa.Column("agent_run_id", sa.Uuid(), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('running', 'completed', 'abstained', 'outcome_unknown')", name="ck_weekly_review_results_status"), sa.CheckConstraint("facts_digest ~ '^[a-f0-9]{64}$'", name="ck_weekly_review_results_facts_digest"), sa.CheckConstraint("result_digest ~ '^[a-f0-9]{64}$'", name="ck_weekly_review_results_result_digest"), sa.CheckConstraint("(status = 'completed' AND advice IS NOT NULL AND abstention_code IS NULL) OR (status = 'abstained' AND advice IS NULL AND abstention_code IS NOT NULL) OR (status IN ('running', 'outcome_unknown') AND advice IS NULL)", name="ck_weekly_review_results_safe_payload"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_weekly_review_results_user", ondelete="CASCADE"), sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], name="fk_weekly_review_results_run", ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id", name="pk_weekly_review_results"), sa.UniqueConstraint("user_id", "week_start", "facts_digest", "graph_version", "prompt_version", "schema_version", "runtime_config_version", name="uq_weekly_review_results_cache_key"),
    )
    op.create_index("ix_weekly_review_results_user_week", "weekly_review_results", ["user_id", "week_start"])


def downgrade() -> None:
    op.drop_index("ix_weekly_review_results_user_week", table_name="weekly_review_results")
    op.drop_table("weekly_review_results")
