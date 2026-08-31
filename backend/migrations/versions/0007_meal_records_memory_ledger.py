"""Create confirmed meal snapshots and local preference-memory authorization ledger.

Revision ID: 0007
Revises: 0006
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "meal_records",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source_run_id", sa.Uuid(), nullable=False), sa.Column("agent_thread_id", sa.Uuid(), nullable=False),
        sa.Column("agent_run_id", sa.Uuid(), nullable=False), sa.Column("command_key", sa.String(128), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=False), sa.Column("nutrition_catalog_version", sa.String(80), nullable=False),
        sa.Column("calculation_version", sa.String(80), nullable=False),
        sa.Column("energy_kcal", sa.Numeric(14, 6), nullable=False), sa.Column("protein_g", sa.Numeric(14, 6), nullable=False),
        sa.Column("fat_g", sa.Numeric(14, 6), nullable=False), sa.Column("carbohydrate_g", sa.Numeric(14, 6), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("energy_kcal >= 0 AND protein_g >= 0 AND fat_g >= 0 AND carbohydrate_g >= 0", name="ck_meal_records_nonnegative_totals"),
        sa.CheckConstraint("consumed_at <= updated_at", name="ck_meal_records_consumed_before_update"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_meal_records_user_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_run_id"], ["agent_runs.id"], name="fk_meal_records_source_run_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["agent_thread_id"], ["agent_threads.id"], name="fk_meal_records_agent_thread_id", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], name="fk_meal_records_agent_run_id", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_meal_records"), sa.UniqueConstraint("user_id", "source_run_id", name="uq_meal_records_user_source_run"),
        sa.UniqueConstraint("user_id", "command_key", name="uq_meal_records_user_command_key"),
    )
    op.create_index("ix_meal_records_user_consumed_active", "meal_records", ["user_id", "consumed_at", "id"], unique=False, postgresql_where=sa.text("deleted_at IS NULL"))
    op.create_table(
        "meal_record_items",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("record_id", sa.Uuid(), nullable=False), sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False), sa.Column("display_name", sa.String(200), nullable=False), sa.Column("food_reference", sa.String(120), nullable=False),
        sa.Column("grams", sa.Numeric(14, 6), nullable=False), sa.Column("energy_kcal", sa.Numeric(14, 6), nullable=False), sa.Column("protein_g", sa.Numeric(14, 6), nullable=False),
        sa.Column("fat_g", sa.Numeric(14, 6), nullable=False), sa.Column("carbohydrate_g", sa.Numeric(14, 6), nullable=False), sa.Column("is_estimated", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("position >= 0", name="ck_meal_record_items_position_nonnegative"), sa.CheckConstraint("grams > 0", name="ck_meal_record_items_grams_positive"),
        sa.CheckConstraint("energy_kcal >= 0 AND protein_g >= 0 AND fat_g >= 0 AND carbohydrate_g >= 0", name="ck_meal_record_items_nonnegative_nutrients"),
        sa.ForeignKeyConstraint(["record_id"], ["meal_records.id"], name="fk_meal_record_items_record_id", ondelete="CASCADE"), sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_meal_record_items_user_id", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_meal_record_items"), sa.UniqueConstraint("record_id", "position", name="uq_meal_record_items_record_position"),
    )
    op.create_index("ix_meal_record_items_record_position", "meal_record_items", ["record_id", "position"], unique=False)
    op.create_table(
        "preference_memory_ledger",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("user_id", sa.Uuid(), nullable=False), sa.Column("category", sa.String(32), nullable=False),
        sa.Column("source_kind", sa.String(32), nullable=False), sa.Column("canonical_text", sa.Text(), nullable=False), sa.Column("external_memory_id", sa.String(160), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("category IN ('goal', 'avoidance', 'stable_preference')", name="ck_preference_memory_ledger_category"),
        sa.CheckConstraint("source_kind IN ('user_statement', 'model_inference', 'user_maintained')", name="ck_preference_memory_ledger_source_kind"), sa.CheckConstraint("canonical_text = btrim(canonical_text) AND canonical_text <> ''", name="ck_preference_memory_ledger_canonical_text"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_preference_memory_ledger_user_id", ondelete="CASCADE"), sa.PrimaryKeyConstraint("id", name="pk_preference_memory_ledger"),
    )
    op.create_index("ix_preference_memory_ledger_user_active", "preference_memory_ledger", ["user_id", "category", "updated_at"], unique=False, postgresql_where=sa.text("is_active"))
    op.create_table(
        "memory_deletion_outbox",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("user_id", sa.Uuid(), nullable=False), sa.Column("ledger_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(48), nullable=False), sa.Column("attempt", sa.Integer(), nullable=False), sa.Column("not_before", sa.DateTime(timezone=True), nullable=False), sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("operation IN ('delete_external_memory')", name="ck_memory_deletion_outbox_operation"), sa.CheckConstraint("status IN ('pending', 'processing', 'completed', 'failed')", name="ck_memory_deletion_outbox_status"), sa.CheckConstraint("attempt >= 0", name="ck_memory_deletion_outbox_attempt"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_memory_deletion_outbox_user_id", ondelete="CASCADE"), sa.ForeignKeyConstraint(["ledger_id"], ["preference_memory_ledger.id"], name="fk_memory_deletion_outbox_ledger_id", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_memory_deletion_outbox"), sa.UniqueConstraint("ledger_id", "operation", name="uq_memory_deletion_outbox_ledger_operation"),
    )
    op.create_index("ix_memory_deletion_outbox_status_not_before", "memory_deletion_outbox", ["status", "not_before"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_memory_deletion_outbox_status_not_before", table_name="memory_deletion_outbox")
    op.drop_table("memory_deletion_outbox")
    op.drop_index("ix_preference_memory_ledger_user_active", table_name="preference_memory_ledger")
    op.drop_table("preference_memory_ledger")
    op.drop_index("ix_meal_record_items_record_position", table_name="meal_record_items")
    op.drop_table("meal_record_items")
    op.drop_index("ix_meal_records_user_consumed_active", table_name="meal_records")
    op.drop_table("meal_records")
