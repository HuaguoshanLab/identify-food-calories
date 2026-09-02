"""Add append-only generic evidence for administrative commands.

Revision ID: 0016
Revises: 0015
Create Date: 2026-09-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_identifier", sa.String(length=320), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("object_type", sa.String(length=80), nullable=False),
        sa.Column("object_id", sa.String(length=160), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("before_diff", sa.JSON(), nullable=False),
        sa.Column("after_diff", sa.JSON(), nullable=False),
        sa.Column("related_version", sa.String(length=120), nullable=True),
        sa.Column("command_key", sa.String(length=160), nullable=False),
        sa.CheckConstraint("actor_identifier = btrim(actor_identifier) AND actor_identifier <> ''", name="ck_admin_audit_events_actor_identifier"),
        sa.CheckConstraint("action = btrim(action) AND action <> ''", name="ck_admin_audit_events_action"),
        sa.CheckConstraint("object_type = btrim(object_type) AND object_type <> ''", name="ck_admin_audit_events_object_type"),
        sa.CheckConstraint("object_id = btrim(object_id) AND object_id <> ''", name="ck_admin_audit_events_object_id"),
        sa.CheckConstraint("reason = btrim(reason) AND reason <> ''", name="ck_admin_audit_events_reason"),
        sa.CheckConstraint("command_key = btrim(command_key) AND command_key <> ''", name="ck_admin_audit_events_command_key"),
        sa.PrimaryKeyConstraint("id", name="pk_admin_audit_events"),
        sa.UniqueConstraint("command_key", name="uq_admin_audit_events_command_key"),
    )
    op.create_index("ix_admin_audit_events_occurred_id", "admin_audit_events", ["occurred_at", "id"])
    op.create_index("ix_admin_audit_events_action_occurred_id", "admin_audit_events", ["action", "occurred_at", "id"])
    op.create_index("ix_admin_audit_events_object_occurred_id", "admin_audit_events", ["object_type", "object_id", "occurred_at", "id"])
    op.create_index("ix_admin_audit_events_actor_occurred_id", "admin_audit_events", ["actor_identifier", "occurred_at", "id"])
    op.execute("""
        CREATE FUNCTION prevent_admin_audit_event_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'admin audit events are append-only';
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_admin_audit_events_append_only
        BEFORE UPDATE OR DELETE ON admin_audit_events
        FOR EACH ROW EXECUTE FUNCTION prevent_admin_audit_event_mutation()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER trg_admin_audit_events_append_only ON admin_audit_events")
    op.execute("DROP FUNCTION prevent_admin_audit_event_mutation()")
    op.drop_index("ix_admin_audit_events_actor_occurred_id", table_name="admin_audit_events")
    op.drop_index("ix_admin_audit_events_object_occurred_id", table_name="admin_audit_events")
    op.drop_index("ix_admin_audit_events_action_occurred_id", table_name="admin_audit_events")
    op.drop_index("ix_admin_audit_events_occurred_id", table_name="admin_audit_events")
    op.drop_table("admin_audit_events")
