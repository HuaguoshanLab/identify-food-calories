"""Add auditable direct-memory provisioning state.

Revision ID: 0009_direct_memory_provisioning
Revises: 0008_retrieval_pgvector_metadata
Create Date: 2026-09-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("preference_memory_ledger", sa.Column("source_run_id", sa.Uuid(), nullable=True))
    op.add_column("preference_memory_ledger", sa.Column("request_key_digest", sa.String(length=64), nullable=True))
    op.add_column("memory_deletion_outbox", sa.Column("request_key", sa.String(length=64), nullable=True))
    op.add_column(
        "preference_memory_ledger",
        sa.Column("provisioning_status", sa.String(length=24), nullable=False, server_default="provisioned"),
    )
    op.create_foreign_key(
        "fk_preference_memory_ledger_source_run_id",
        "preference_memory_ledger",
        "agent_runs",
        ["source_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_preference_memory_ledger_provisioning_status",
        "preference_memory_ledger",
        "provisioning_status IN ('pending', 'claimed', 'provisioned', 'outcome_unknown', 'failed', 'cancelled')",
    )
    op.create_index(
        "uq_preference_memory_ledger_source_run_request",
        "preference_memory_ledger",
        ["user_id", "source_run_id", "category", "request_key_digest"],
        unique=True,
        postgresql_where=sa.text("source_run_id IS NOT NULL AND request_key_digest IS NOT NULL"),
    )
    op.create_index(
        "uq_preference_memory_ledger_active_canonical",
        "preference_memory_ledger",
        ["user_id", "category", "canonical_text"],
        unique=True,
        postgresql_where=sa.text("is_active AND deleted_at IS NULL"),
    )
    op.create_table(
        "memory_provision_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("ledger_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(length=48), nullable=False),
        sa.Column("request_key", sa.String(length=64), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("not_before", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("operation IN ('provision_external_memory')", name="ck_memory_provision_outbox_operation"),
        sa.CheckConstraint("status IN ('pending', 'claimed', 'provisioned', 'outcome_unknown', 'failed', 'cancelled')", name="ck_memory_provision_outbox_status"),
        sa.CheckConstraint("attempt >= 0", name="ck_memory_provision_outbox_attempt"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_memory_provision_outbox_user_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ledger_id"], ["preference_memory_ledger.id"], name="fk_memory_provision_outbox_ledger_id", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_memory_provision_outbox"),
        sa.UniqueConstraint("ledger_id", "operation", name="uq_memory_provision_outbox_ledger_operation"),
    )
    op.create_index(
        "ix_memory_provision_outbox_status_not_before",
        "memory_provision_outbox",
        ["status", "not_before"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_memory_provision_outbox_status_not_before", table_name="memory_provision_outbox")
    op.drop_table("memory_provision_outbox")
    op.drop_index("uq_preference_memory_ledger_active_canonical", table_name="preference_memory_ledger")
    op.drop_index("uq_preference_memory_ledger_source_run_request", table_name="preference_memory_ledger")
    op.drop_constraint("ck_preference_memory_ledger_provisioning_status", "preference_memory_ledger", type_="check")
    op.drop_constraint("fk_preference_memory_ledger_source_run_id", "preference_memory_ledger", type_="foreignkey")
    op.drop_column("preference_memory_ledger", "provisioning_status")
    op.drop_column("preference_memory_ledger", "request_key_digest")
    op.drop_column("preference_memory_ledger", "source_run_id")
    op.drop_column("memory_deletion_outbox", "request_key")
