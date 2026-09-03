"""Add immutable non-secret reasoning runtime configuration snapshots.

Phase 06's draft reserved 0017, but completed catalog work already occupies
0017 and 0018. The user authorized this successor to continue the actual
single-head lineage instead of creating a parallel revision.

Revision ID: 0019
Revises: 0018
Create Date: 2026-09-03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_runtime_config_versions",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False), sa.Column("model_alias", sa.String(length=120), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False), sa.Column("single_call_cap_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("period_cap_usd", sa.Numeric(12, 6), nullable=False), sa.Column("input_usd_per_m", sa.Numeric(12, 6), nullable=False),
        sa.Column("output_usd_per_m", sa.Numeric(12, 6), nullable=False), sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False), sa.Column("command_key", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.PrimaryKeyConstraint("id", name="pk_agent_runtime_config_versions"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("version", name="uq_agent_runtime_config_versions_version"),
        sa.UniqueConstraint("command_key", name="uq_agent_runtime_config_versions_command_key"),
        sa.CheckConstraint("version > 0", name="ck_agent_runtime_config_versions_positive"),
        sa.CheckConstraint("provider IN ('deepseek')", name="ck_agent_runtime_config_provider"),
        sa.CheckConstraint("model_alias IN ('deepseek-v4-flash')", name="ck_agent_runtime_config_model"),
        sa.CheckConstraint("single_call_cap_usd >= 0", name="ck_agent_runtime_config_single_cap"),
        sa.CheckConstraint("period_cap_usd >= 0", name="ck_agent_runtime_config_period_cap"),
        sa.CheckConstraint("input_usd_per_m >= 0 AND output_usd_per_m >= 0", name="ck_agent_runtime_config_prices"),
        sa.CheckConstraint("reason = btrim(reason) AND reason <> ''", name="ck_agent_runtime_config_reason"),
    )
    op.create_index("ix_agent_runtime_config_versions_created", "agent_runtime_config_versions", ["created_at", "id"])
    with op.batch_alter_table("agent_runs") as batch:
        batch.add_column(sa.Column("runtime_config_version_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("runtime_config_snapshot", sa.JSON(), nullable=True))
        batch.create_foreign_key("fk_agent_runs_runtime_config_version_id", "agent_runtime_config_versions", ["runtime_config_version_id"], ["id"], ondelete="RESTRICT")
    with op.batch_alter_table("agent_invocations") as batch:
        batch.add_column(sa.Column("runtime_config_version_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("price_cap_snapshot", sa.JSON(), nullable=True))
        batch.create_foreign_key("fk_agent_invocations_runtime_config_version_id", "agent_runtime_config_versions", ["runtime_config_version_id"], ["id"], ondelete="RESTRICT")


def downgrade() -> None:
    with op.batch_alter_table("agent_invocations") as batch:
        batch.drop_constraint("fk_agent_invocations_runtime_config_version_id", type_="foreignkey")
        batch.drop_column("price_cap_snapshot")
        batch.drop_column("runtime_config_version_id")
    with op.batch_alter_table("agent_runs") as batch:
        batch.drop_constraint("fk_agent_runs_runtime_config_version_id", type_="foreignkey")
        batch.drop_column("runtime_config_snapshot")
        batch.drop_column("runtime_config_version_id")
    op.drop_index("ix_agent_runtime_config_versions_created", table_name="agent_runtime_config_versions")
    op.drop_table("agent_runtime_config_versions")
