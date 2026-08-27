"""Create authoritative authentication, verification, and session schema.

Revision ID: 0001
Revises: None
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=16), server_default="user", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("email = lower(btrim(email))", name="ck_users_email_normalized"),
        sa.CheckConstraint("role IN ('user', 'admin')", name="ck_users_role"),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "verification_challenges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("context_digest", sa.String(length=128), nullable=False),
        sa.Column("code_digest", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="5", nullable=False),
        sa.Column("resend_available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "purpose IN ('registration', 'password_reset')",
            name="ck_verification_challenges_purpose",
        ),
        sa.CheckConstraint(
            "expires_at > created_at", name="ck_verification_challenges_expiry"
        ),
        sa.CheckConstraint(
            "resend_available_at >= created_at AND resend_available_at <= expires_at",
            name="ck_verification_challenges_resend_window",
        ),
        sa.CheckConstraint(
            "attempts >= 0 AND max_attempts > 0 AND attempts <= max_attempts",
            name="ck_verification_challenges_attempts",
        ),
        sa.CheckConstraint(
            "consumed_at IS NULL OR consumed_at >= created_at",
            name="ck_verification_challenges_consumed_at",
        ),
        sa.CheckConstraint(
            "invalidated_at IS NULL OR invalidated_at >= created_at",
            name="ck_verification_challenges_invalidated_at",
        ),
        sa.CheckConstraint(
            "NOT (consumed_at IS NOT NULL AND invalidated_at IS NOT NULL)",
            name="ck_verification_challenges_terminal_state",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_verification_challenges_user_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_verification_challenges"),
        sa.UniqueConstraint("context_digest", name="uq_verification_challenges_context_digest"),
        sa.UniqueConstraint("code_digest", name="uq_verification_challenges_code_digest"),
    )
    op.create_index(
        "uq_verification_challenges_current",
        "verification_challenges",
        ["user_id", "purpose"],
        unique=True,
        postgresql_where=sa.text("consumed_at IS NULL AND invalidated_at IS NULL"),
    )

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("device_label", sa.String(length=160), nullable=True),
        sa.CheckConstraint("expires_at > created_at", name="ck_auth_sessions_expiry"),
        sa.CheckConstraint("last_seen_at >= created_at", name="ck_auth_sessions_last_seen"),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at", name="ck_auth_sessions_revoked_at"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_auth_sessions_user_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_sessions"),
        sa.UniqueConstraint("family_id", name="uq_auth_sessions_family_id"),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index(
        "ix_auth_sessions_active_expiry",
        "auth_sessions",
        ["expires_at"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("token_digest", sa.String(length=128), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_id", sa.Uuid(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("expires_at > issued_at", name="ck_refresh_tokens_expiry"),
        sa.CheckConstraint(
            "consumed_at IS NULL OR consumed_at >= issued_at", name="ck_refresh_tokens_consumed_at"
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= issued_at", name="ck_refresh_tokens_revoked_at"
        ),
        sa.CheckConstraint(
            "replaced_by_id IS NULL OR consumed_at IS NOT NULL",
            name="ck_refresh_tokens_replacement_requires_consumption",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["auth_sessions.id"], name="fk_refresh_tokens_session_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["replaced_by_id"], ["refresh_tokens.id"], name="fk_refresh_tokens_replaced_by_id", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_refresh_tokens"),
        sa.UniqueConstraint("token_digest", name="uq_refresh_tokens_token_digest"),
    )
    op.create_index("ix_refresh_tokens_session_id", "refresh_tokens", ["session_id"])
    op.create_index(
        "ix_refresh_tokens_active_expiry",
        "refresh_tokens",
        ["expires_at"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_active_expiry", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_session_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index("ix_auth_sessions_active_expiry", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index(
        "uq_verification_challenges_current", table_name="verification_challenges"
    )
    op.drop_table("verification_challenges")
    op.drop_table("users")
