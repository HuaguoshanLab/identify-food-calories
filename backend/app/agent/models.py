"""Authoritative, minimal Agent ledger models.

LangGraph checkpoints are intentionally not represented here.  These tables own
tenant binding, durable execution idempotency and safe audit metadata; checkpoint
state remains a short-lived implementation detail managed by the checkpointer.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.auth.models import Base


class AgentThread(Base):
    """One user-owned conversational thread; the UUID is never an authority token."""

    __tablename__ = "agent_threads"
    __table_args__ = (
        CheckConstraint("revision >= 0", name="ck_agent_threads_revision_nonnegative"),
        CheckConstraint(
            "status IN ('open', 'waiting_input', 'completed', 'failed', 'deleted')",
            name="ck_agent_threads_status",
        ),
        UniqueConstraint("user_id", "id", name="uq_agent_threads_user_id"),
        Index("ix_agent_threads_user_last_activity", "user_id", "last_activity_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentRun(Base):
    """A durable command/run record with a canonical request hash for idempotency."""

    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint("model_calls >= 0", name="ck_agent_runs_model_calls_nonnegative"),
        CheckConstraint("tool_calls >= 0", name="ck_agent_runs_tool_calls_nonnegative"),
        CheckConstraint("graph_steps >= 0", name="ck_agent_runs_graph_steps_nonnegative"),
        CheckConstraint("elapsed_ms >= 0", name="ck_agent_runs_elapsed_nonnegative"),
        CheckConstraint("estimated_cost_usd >= 0", name="ck_agent_runs_cost_nonnegative"),
        CheckConstraint(
            "status IN ('accepted', 'running', 'waiting_input', 'completed', 'failed', 'limit_reached')",
            name="ck_agent_runs_status",
        ),
        UniqueConstraint(
            "thread_id", "command_key", name="uq_agent_runs_thread_command_key"
        ),
        UniqueConstraint("user_id", "thread_id", "id", name="uq_agent_runs_user_thread_id"),
        Index("ix_agent_runs_user_created", "user_id", "created_at"),
        Index("ix_agent_runs_thread_created", "thread_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("agent_threads.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    command_key: Mapped[str] = mapped_column(String(128), nullable=False)
    command_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="accepted")
    graph_version: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False)
    tool_version: Mapped[str] = mapped_column(String(80), nullable=False)
    model_provider: Mapped[str | None] = mapped_column(String(80))
    model_version: Mapped[str | None] = mapped_column(String(120))
    graph_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    model_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tool_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    elapsed_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("0")
    )
    failure_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentEvent(Base):
    """Append-only, client-safe event metadata; raw State and provider bodies are excluded."""

    __tablename__ = "agent_events"
    __table_args__ = (
        CheckConstraint("seq > 0", name="ck_agent_events_seq_positive"),
        UniqueConstraint("thread_id", "seq", name="uq_agent_events_thread_seq"),
        Index("ix_agent_events_user_thread_seq", "user_id", "thread_id", "seq"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("agent_threads.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("agent_runs.id", ondelete="SET NULL")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    safe_summary: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AgentInvocation(Base):
    """Idempotency ledger for provider/tool side effects, keyed without request bodies."""

    __tablename__ = "agent_invocations"
    __table_args__ = (
        CheckConstraint("attempt >= 0", name="ck_agent_invocations_attempt_nonnegative"),
        CheckConstraint("cost_usd >= 0", name="ck_agent_invocations_cost_nonnegative"),
        CheckConstraint(
            "status IN ('prepared', 'completed', 'failed', 'outcome_unknown')",
            name="ck_agent_invocations_status",
        ),
        UniqueConstraint(
            "run_id",
            "node_name",
            "item_key",
            "input_version",
            "operation_version",
            "request_hash",
            name="uq_agent_invocations_idempotency",
        ),
        Index("ix_agent_invocations_run_created", "run_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("agent_threads.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    node_name: Mapped[str] = mapped_column(String(80), nullable=False)
    item_key: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    input_version: Mapped[str] = mapped_column(String(80), nullable=False)
    operation_version: Mapped[str] = mapped_column(String(80), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="prepared")
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, default=Decimal("0")
    )
    safe_result_digest: Mapped[str | None] = mapped_column(String(64))
    failure_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AgentImage(Base):
    """Minimal durable lifecycle metadata for one normalized, private image handle."""

    __tablename__ = "agent_images"
    __table_args__ = (
        CheckConstraint("digest_sha256 ~ '^[a-f0-9]{64}$'", name="ck_agent_images_digest"),
        CheckConstraint(
            "mime_type IN ('image/jpeg', 'image/png', 'image/webp')",
            name="ck_agent_images_mime",
        ),
        CheckConstraint("width > 0 AND height > 0 AND byte_size > 0", name="ck_agent_images_dimensions"),
        CheckConstraint(
            "status IN ('ready', 'processing', 'deletion_pending', 'deleted', 'delete_failed')",
            name="ck_agent_images_status",
        ),
        UniqueConstraint("run_id", "locator", name="uq_agent_images_run_locator"),
        Index("ix_agent_images_user_thread", "user_id", "thread_id"),
        Index("ix_agent_images_status_expiry", "status", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("agent_threads.id", ondelete="CASCADE"), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    digest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(32), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    locator: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ready")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AgentVisionInvocation(Base):
    """Provider-safe invocation ledger: no prompt, image payload, or model body survives."""

    __tablename__ = "agent_vision_invocations"
    __table_args__ = (
        CheckConstraint("attempt >= 0", name="ck_agent_vision_invocations_attempt"),
        CheckConstraint("cost_cny >= 0", name="ck_agent_vision_invocations_cost"),
        CheckConstraint(
            "status IN ('prepared', 'running', 'completed', 'failed', 'outcome_unknown')",
            name="ck_agent_vision_invocations_status",
        ),
        UniqueConstraint("image_id", "request_key", name="uq_agent_vision_invocations_image_request"),
        Index("ix_agent_vision_invocations_user_run", "user_id", "run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    image_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("agent_images.id", ondelete="CASCADE"), nullable=False)
    thread_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("agent_threads.id", ondelete="CASCADE"), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    request_key: Mapped[str] = mapped_column(String(128), nullable=False)
    model_alias: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_request_id: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="prepared")
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_cny: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=Decimal("0"))
    safe_result_digest: Mapped[str | None] = mapped_column(String(64))
    failure_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AgentLease(Base):
    """A PostgreSQL-coordinated execution lease; workers never use process-local locks."""

    __tablename__ = "agent_leases"
    __table_args__ = (
        CheckConstraint("expires_at > acquired_at", name="ck_agent_leases_expiry"),
        UniqueConstraint("run_id", name="uq_agent_leases_run"),
        Index("ix_agent_leases_expiry", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False
    )
    holder_id: Mapped[str] = mapped_column(String(128), nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AgentDeletionIntent(Base):
    """A durable, tenant-bound request for later bounded cascade deletion."""

    __tablename__ = "agent_deletion_intents"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'completed', 'failed')",
            name="ck_agent_deletion_intents_status",
        ),
        CheckConstraint(
            "purge_after >= requested_at", name="ck_agent_deletion_intents_purge_after"
        ),
        UniqueConstraint("thread_id", name="uq_agent_deletion_intents_thread"),
        Index(
            "ix_agent_deletion_intents_status_purge_after", "status", "purge_after"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("agent_threads.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    purge_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
