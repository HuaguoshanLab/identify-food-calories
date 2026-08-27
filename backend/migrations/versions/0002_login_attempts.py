"""Create opaque database-authoritative login attempt buckets.

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "login_attempts",
        sa.Column("bucket_digest", sa.String(length=64), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "failed_attempts > 0", name="ck_login_attempts_positive"
        ),
        sa.CheckConstraint(
            "window_expires_at > window_started_at",
            name="ck_login_attempts_window",
        ),
        sa.CheckConstraint(
            "blocked_until IS NULL OR blocked_until > window_started_at",
            name="ck_login_attempts_blocked_until",
        ),
        sa.PrimaryKeyConstraint("bucket_digest", name="pk_login_attempts"),
    )
    op.create_index(
        "ix_login_attempts_blocked_until", "login_attempts", ["blocked_until"]
    )


def downgrade() -> None:
    op.drop_index("ix_login_attempts_blocked_until", table_name="login_attempts")
    op.drop_table("login_attempts")
