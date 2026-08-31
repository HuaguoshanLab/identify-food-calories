"""Persist minimal, tenant-bound image and vision invocation metadata.

Revision ID: 0006
Revises: 0005
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Only opaque, deletion-capable references cross this durable boundary. Image bytes,
    # names, metadata and public URLs are deliberately absent from the schema.
    op.create_table(
        "agent_images",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("digest_sha256", sa.String(length=64), nullable=False),
        sa.Column("mime_type", sa.String(length=32), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("locator", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("digest_sha256 ~ '^[a-f0-9]{64}$'", name="ck_agent_images_digest"),
        sa.CheckConstraint("mime_type IN ('image/jpeg', 'image/png', 'image/webp')", name="ck_agent_images_mime"),
        sa.CheckConstraint("width > 0 AND height > 0 AND byte_size > 0", name="ck_agent_images_dimensions"),
        sa.CheckConstraint("status IN ('ready', 'processing', 'deletion_pending', 'deleted', 'delete_failed')", name="ck_agent_images_status"),
        sa.ForeignKeyConstraint(["thread_id"], ["agent_threads.id"], name="fk_agent_images_thread_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], name="fk_agent_images_run_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_agent_images_user_id", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_agent_images"),
        sa.UniqueConstraint("run_id", "locator", name="uq_agent_images_run_locator"),
    )
    op.create_index("ix_agent_images_user_thread", "agent_images", ["user_id", "thread_id"])
    op.create_index("ix_agent_images_status_expiry", "agent_images", ["status", "expires_at"])
    op.create_table(
        "agent_vision_invocations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("image_id", sa.Uuid(), nullable=False),
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("request_key", sa.String(length=128), nullable=False),
        sa.Column("model_alias", sa.String(length=128), nullable=False),
        sa.Column("provider_request_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("cost_cny", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("safe_result_digest", sa.String(length=64), nullable=True),
        sa.Column("failure_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("attempt >= 0", name="ck_agent_vision_invocations_attempt"),
        sa.CheckConstraint("cost_cny >= 0", name="ck_agent_vision_invocations_cost"),
        sa.CheckConstraint("status IN ('prepared', 'running', 'completed', 'failed', 'outcome_unknown')", name="ck_agent_vision_invocations_status"),
        sa.ForeignKeyConstraint(["image_id"], ["agent_images.id"], name="fk_agent_vision_invocations_image_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["thread_id"], ["agent_threads.id"], name="fk_agent_vision_invocations_thread_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], name="fk_agent_vision_invocations_run_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_agent_vision_invocations_user_id", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_agent_vision_invocations"),
        sa.UniqueConstraint("image_id", "request_key", name="uq_agent_vision_invocations_image_request"),
    )
    op.create_index("ix_agent_vision_invocations_user_run", "agent_vision_invocations", ["user_id", "run_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_vision_invocations_user_run", table_name="agent_vision_invocations")
    op.drop_table("agent_vision_invocations")
    op.drop_index("ix_agent_images_status_expiry", table_name="agent_images")
    op.drop_index("ix_agent_images_user_thread", table_name="agent_images")
    op.drop_table("agent_images")
