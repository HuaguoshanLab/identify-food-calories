"""Create immutable evidence for admin role elevation.

Revision ID: 0003
Revises: 0002
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "admin_role_audit",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_identifier", sa.String(length=320), nullable=False),
        sa.Column("target_user_id", sa.Uuid(), nullable=False),
        sa.Column("before_role", sa.String(length=16), nullable=False),
        sa.Column("after_role", sa.String(length=16), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.CheckConstraint(
            "actor_identifier = btrim(actor_identifier) AND actor_identifier <> ''",
            name="ck_admin_role_audit_actor_identifier",
        ),
        sa.CheckConstraint(
            "before_role IN ('user', 'admin')", name="ck_admin_role_audit_before_role"
        ),
        sa.CheckConstraint(
            "after_role IN ('user', 'admin')", name="ck_admin_role_audit_after_role"
        ),
        sa.CheckConstraint(
            "before_role <> after_role", name="ck_admin_role_audit_role_transition"
        ),
        sa.CheckConstraint(
            "reason = btrim(reason) AND reason <> ''",
            name="ck_admin_role_audit_reason",
        ),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id", name="pk_admin_role_audit"),
    )
    op.create_index(
        "ix_admin_role_audit_target_occurred_at",
        "admin_role_audit",
        ["target_user_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_admin_role_audit_target_occurred_at", table_name="admin_role_audit")
    op.drop_table("admin_role_audit")
