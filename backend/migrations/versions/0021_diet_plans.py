"""Persist daily plans and immutable recipe/nutrition snapshots outside Agent retention."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "diet_plans",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("plan_date", sa.Date(), nullable=False),
        sa.Column("time_zone", sa.String(100), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("user_id", "id", name="uq_diet_plans_user_id"),
        sa.CheckConstraint("current_version >= 1", name="ck_diet_plans_version"),
    )
    op.create_index(
        "uq_diet_plans_active_day",
        "diet_plans",
        ["user_id", "plan_date"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "diet_plan_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source_run_id", sa.Uuid(), nullable=False),
        sa.Column("source_thread_id", sa.Uuid(), nullable=False),
        sa.Column("report", postgresql.JSONB(none_as_null=True)),
        sa.Column("totals", postgresql.JSONB(none_as_null=True)),
        sa.Column("provenance", postgresql.JSONB(none_as_null=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id", "plan_id"],
            ["diet_plans.user_id", "diet_plans.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "user_id", "source_run_id", name="uq_diet_plan_versions_run"
        ),
        sa.UniqueConstraint("plan_id", "version", name="uq_diet_plan_versions_number"),
        sa.CheckConstraint("version >= 1", name="ck_diet_plan_versions_number"),
    )
    op.create_index(
        "ix_diet_plan_versions_thread",
        "diet_plan_versions",
        ["user_id", "source_thread_id"],
    )


def downgrade() -> None:
    op.drop_table("diet_plan_versions")
    op.drop_table("diet_plans")
