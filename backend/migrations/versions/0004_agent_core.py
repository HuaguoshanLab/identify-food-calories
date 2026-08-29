"""Create Agent ledger and nutrition catalog schema without business seed data.

Revision ID: 0004
Revises: 0003
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Schema and data lifecycles differ: versioned catalog records arrive through the
    # audited importer, so this revision intentionally creates no business records.
    op.create_table(
        "nutrition_catalogs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("catalog_key", sa.String(length=80), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "catalog_key = btrim(catalog_key) AND catalog_key <> ''",
            name="ck_nutrition_catalogs_key",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_nutrition_catalogs"),
        sa.UniqueConstraint("catalog_key", name="uq_nutrition_catalogs_key"),
    )
    op.create_table(
        "nutrition_catalog_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("catalog_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.String(length=80), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "version = btrim(version) AND version <> ''",
            name="ck_nutrition_catalog_versions_version",
        ),
        sa.ForeignKeyConstraint(
            ["catalog_id"], ["nutrition_catalogs.id"],
            name="fk_nutrition_catalog_versions_catalog_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_nutrition_catalog_versions"),
        sa.UniqueConstraint(
            "catalog_id", "version", name="uq_nutrition_catalog_versions_catalog_version"
        ),
    )
    op.create_index(
        "ix_nutrition_catalog_versions_catalog_released",
        "nutrition_catalog_versions",
        ["catalog_id", "released_at"],
    )
    op.create_table(
        "nutrition_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("catalog_version_id", sa.Uuid(), nullable=False),
        sa.Column("source_name", sa.String(length=120), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=False),
        sa.Column("license_name", sa.String(length=120), nullable=False),
        sa.CheckConstraint(
            "source_name = btrim(source_name) AND source_name <> ''",
            name="ck_nutrition_sources_name",
        ),
        sa.CheckConstraint(
            "source_url = btrim(source_url) AND source_url <> ''",
            name="ck_nutrition_sources_url",
        ),
        sa.CheckConstraint(
            "license_name = btrim(license_name) AND license_name <> ''",
            name="ck_nutrition_sources_license",
        ),
        sa.ForeignKeyConstraint(
            ["catalog_version_id"], ["nutrition_catalog_versions.id"],
            name="fk_nutrition_sources_catalog_version_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_nutrition_sources"),
        sa.UniqueConstraint(
            "catalog_version_id", "source_url", name="uq_nutrition_sources_version_url"
        ),
    )
    op.create_table(
        "food_catalog_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("catalog_version_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("stable_id", sa.String(length=120), nullable=False),
        sa.Column("canonical_name", sa.String(length=200), nullable=False),
        sa.Column("prepared_state", sa.String(length=120), nullable=False),
        sa.Column("is_qualified", sa.Boolean(), nullable=False),
        sa.Column("energy_kcal_per_100g", sa.Numeric(precision=14, scale=6), nullable=True),
        sa.Column("protein_g_per_100g", sa.Numeric(precision=14, scale=6), nullable=True),
        sa.Column("fat_g_per_100g", sa.Numeric(precision=14, scale=6), nullable=True),
        sa.Column("carbohydrate_g_per_100g", sa.Numeric(precision=14, scale=6), nullable=True),
        sa.CheckConstraint(
            "stable_id = btrim(stable_id) AND stable_id <> ''",
            name="ck_food_catalog_items_stable_id",
        ),
        sa.CheckConstraint(
            "canonical_name = btrim(canonical_name) AND canonical_name <> ''",
            name="ck_food_catalog_items_canonical_name",
        ),
        sa.CheckConstraint(
            "prepared_state = btrim(prepared_state) AND prepared_state <> ''",
            name="ck_food_catalog_items_prepared_state",
        ),
        sa.CheckConstraint(
            "NOT is_qualified OR (energy_kcal_per_100g IS NOT NULL AND protein_g_per_100g IS NOT NULL AND fat_g_per_100g IS NOT NULL AND carbohydrate_g_per_100g IS NOT NULL)",
            name="ck_food_catalog_items_qualified_nutrients",
        ),
        sa.ForeignKeyConstraint(
            ["catalog_version_id"], ["nutrition_catalog_versions.id"],
            name="fk_food_catalog_items_catalog_version_id", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["nutrition_sources.id"],
            name="fk_food_catalog_items_source_id", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_food_catalog_items"),
        sa.UniqueConstraint(
            "catalog_version_id", "stable_id", name="uq_food_catalog_version_stable_id"
        ),
    )
    op.create_index(
        "ix_food_catalog_items_version_name",
        "food_catalog_items",
        ["catalog_version_id", "canonical_name"],
    )
    op.create_table(
        "food_catalog_aliases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("food_id", sa.Uuid(), nullable=False),
        sa.Column("alias", sa.String(length=200), nullable=False),
        sa.Column("normalized_alias", sa.String(length=200), nullable=False),
        sa.Column("is_controlled", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "alias = btrim(alias) AND alias <> ''", name="ck_food_catalog_aliases_alias"
        ),
        sa.CheckConstraint(
            "normalized_alias = btrim(normalized_alias) AND normalized_alias <> ''",
            name="ck_food_catalog_aliases_normalized_alias",
        ),
        sa.ForeignKeyConstraint(
            ["food_id"], ["food_catalog_items.id"],
            name="fk_food_catalog_aliases_food_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_food_catalog_aliases"),
        sa.UniqueConstraint("food_id", "normalized_alias", name="uq_food_alias_per_food"),
    )
    op.create_index(
        "ix_food_catalog_aliases_normalized_alias",
        "food_catalog_aliases",
        ["normalized_alias"],
    )
    op.create_table(
        "food_catalog_portions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("food_id", sa.Uuid(), nullable=False),
        sa.Column("description", sa.String(length=120), nullable=False),
        sa.Column("grams", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("source_reference", sa.Text(), nullable=False),
        sa.Column("version", sa.String(length=80), nullable=False),
        sa.Column("audited", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "description = btrim(description) AND description <> ''",
            name="ck_food_catalog_portions_description",
        ),
        sa.CheckConstraint("grams > 0", name="ck_food_catalog_portions_grams_positive"),
        sa.CheckConstraint(
            "source_reference = btrim(source_reference) AND source_reference <> ''",
            name="ck_food_catalog_portions_source_reference",
        ),
        sa.CheckConstraint(
            "version = btrim(version) AND version <> ''",
            name="ck_food_catalog_portions_version",
        ),
        sa.ForeignKeyConstraint(
            ["food_id"], ["food_catalog_items.id"],
            name="fk_food_catalog_portions_food_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_food_catalog_portions"),
        sa.UniqueConstraint(
            "food_id", "description", name="uq_food_catalog_portions_food_description"
        ),
    )

    op.create_table(
        "agent_threads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("revision >= 0", name="ck_agent_threads_revision_nonnegative"),
        sa.CheckConstraint(
            "status IN ('open', 'waiting_input', 'completed', 'failed', 'deleted')",
            name="ck_agent_threads_status",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_agent_threads_user_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_agent_threads"),
    )
    op.create_index(
        "ix_agent_threads_user_last_activity",
        "agent_threads",
        ["user_id", "last_activity_at"],
    )
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("command_key", sa.String(length=128), nullable=False),
        sa.Column("command_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("graph_version", sa.String(length=80), nullable=False),
        sa.Column("prompt_version", sa.String(length=80), nullable=False),
        sa.Column("tool_version", sa.String(length=80), nullable=False),
        sa.Column("model_provider", sa.String(length=80), nullable=True),
        sa.Column("model_version", sa.String(length=120), nullable=True),
        sa.Column("graph_steps", sa.Integer(), nullable=False),
        sa.Column("model_calls", sa.Integer(), nullable=False),
        sa.Column("tool_calls", sa.Integer(), nullable=False),
        sa.Column("elapsed_ms", sa.Integer(), nullable=False),
        sa.Column("estimated_cost_usd", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("failure_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("model_calls >= 0", name="ck_agent_runs_model_calls_nonnegative"),
        sa.CheckConstraint("tool_calls >= 0", name="ck_agent_runs_tool_calls_nonnegative"),
        sa.CheckConstraint("graph_steps >= 0", name="ck_agent_runs_graph_steps_nonnegative"),
        sa.CheckConstraint("elapsed_ms >= 0", name="ck_agent_runs_elapsed_nonnegative"),
        sa.CheckConstraint("estimated_cost_usd >= 0", name="ck_agent_runs_cost_nonnegative"),
        sa.CheckConstraint(
            "status IN ('accepted', 'running', 'waiting_input', 'completed', 'failed', 'limit_reached')",
            name="ck_agent_runs_status",
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"], ["agent_threads.id"],
            name="fk_agent_runs_thread_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_agent_runs_user_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_agent_runs"),
        sa.UniqueConstraint("thread_id", "command_key", name="uq_agent_runs_thread_command_key"),
    )
    op.create_index("ix_agent_runs_user_created", "agent_runs", ["user_id", "created_at"])
    op.create_index("ix_agent_runs_thread_created", "agent_runs", ["thread_id", "created_at"])
    op.create_table(
        "agent_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("safe_summary", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("seq > 0", name="ck_agent_events_seq_positive"),
        sa.ForeignKeyConstraint(
            ["thread_id"], ["agent_threads.id"],
            name="fk_agent_events_thread_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["agent_runs.id"], name="fk_agent_events_run_id", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_agent_events_user_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_agent_events"),
        sa.UniqueConstraint("thread_id", "seq", name="uq_agent_events_thread_seq"),
    )
    op.create_index(
        "ix_agent_events_user_thread_seq", "agent_events", ["user_id", "thread_id", "seq"]
    )
    op.create_table(
        "agent_invocations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("node_name", sa.String(length=80), nullable=False),
        sa.Column("item_key", sa.String(length=128), nullable=False),
        sa.Column("input_version", sa.String(length=80), nullable=False),
        sa.Column("operation_version", sa.String(length=80), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("safe_result_digest", sa.String(length=64), nullable=True),
        sa.Column("failure_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("attempt >= 0", name="ck_agent_invocations_attempt_nonnegative"),
        sa.CheckConstraint("cost_usd >= 0", name="ck_agent_invocations_cost_nonnegative"),
        sa.CheckConstraint(
            "status IN ('prepared', 'completed', 'failed', 'outcome_unknown')",
            name="ck_agent_invocations_status",
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"], ["agent_threads.id"],
            name="fk_agent_invocations_thread_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["agent_runs.id"],
            name="fk_agent_invocations_run_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_agent_invocations_user_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_agent_invocations"),
        sa.UniqueConstraint(
            "run_id", "node_name", "item_key", "input_version", "operation_version", "request_hash",
            name="uq_agent_invocations_idempotency",
        ),
    )
    op.create_index(
        "ix_agent_invocations_run_created", "agent_invocations", ["run_id", "created_at"]
    )
    op.create_table(
        "agent_leases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("holder_id", sa.String(length=128), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("expires_at > acquired_at", name="ck_agent_leases_expiry"),
        sa.ForeignKeyConstraint(
            ["run_id"], ["agent_runs.id"], name="fk_agent_leases_run_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_agent_leases"),
        sa.UniqueConstraint("run_id", name="uq_agent_leases_run"),
    )
    op.create_index("ix_agent_leases_expiry", "agent_leases", ["expires_at"])
    op.create_table(
        "agent_deletion_intents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("purge_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'completed', 'failed')",
            name="ck_agent_deletion_intents_status",
        ),
        sa.CheckConstraint(
            "purge_after >= requested_at", name="ck_agent_deletion_intents_purge_after"
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"], ["agent_threads.id"],
            name="fk_agent_deletion_intents_thread_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_agent_deletion_intents_user_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_agent_deletion_intents"),
        sa.UniqueConstraint("thread_id", name="uq_agent_deletion_intents_thread"),
    )
    op.create_index(
        "ix_agent_deletion_intents_status_purge_after",
        "agent_deletion_intents",
        ["status", "purge_after"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_deletion_intents_status_purge_after", table_name="agent_deletion_intents")
    op.drop_table("agent_deletion_intents")
    op.drop_index("ix_agent_leases_expiry", table_name="agent_leases")
    op.drop_table("agent_leases")
    op.drop_index("ix_agent_invocations_run_created", table_name="agent_invocations")
    op.drop_table("agent_invocations")
    op.drop_index("ix_agent_events_user_thread_seq", table_name="agent_events")
    op.drop_table("agent_events")
    op.drop_index("ix_agent_runs_thread_created", table_name="agent_runs")
    op.drop_index("ix_agent_runs_user_created", table_name="agent_runs")
    op.drop_table("agent_runs")
    op.drop_index("ix_agent_threads_user_last_activity", table_name="agent_threads")
    op.drop_table("agent_threads")
    op.drop_table("food_catalog_portions")
    op.drop_index("ix_food_catalog_aliases_normalized_alias", table_name="food_catalog_aliases")
    op.drop_table("food_catalog_aliases")
    op.drop_index("ix_food_catalog_items_version_name", table_name="food_catalog_items")
    op.drop_table("food_catalog_items")
    op.drop_table("nutrition_sources")
    op.drop_index(
        "ix_nutrition_catalog_versions_catalog_released",
        table_name="nutrition_catalog_versions",
    )
    op.drop_table("nutrition_catalog_versions")
    op.drop_table("nutrition_catalogs")
