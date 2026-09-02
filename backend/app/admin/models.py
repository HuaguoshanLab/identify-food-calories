"""ORM state for immutable admin-role change evidence."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.auth.models import Base


class AdminRoleAudit(Base):
    """A persisted role transition, written beside the change it proves."""

    __tablename__ = "admin_role_audit"
    __table_args__ = (
        CheckConstraint(
            "actor_identifier = btrim(actor_identifier) AND actor_identifier <> ''",
            name="ck_admin_role_audit_actor_identifier",
        ),
        CheckConstraint(
            "before_role IN ('user', 'admin')", name="ck_admin_role_audit_before_role"
        ),
        CheckConstraint(
            "after_role IN ('user', 'admin')", name="ck_admin_role_audit_after_role"
        ),
        CheckConstraint(
            "before_role <> after_role", name="ck_admin_role_audit_role_transition"
        ),
        CheckConstraint(
            "reason = btrim(reason) AND reason <> ''",
            name="ck_admin_role_audit_reason",
        ),
        Index("ix_admin_role_audit_target_occurred_at", "target_user_id", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    actor_identifier: Mapped[str] = mapped_column(String(320), nullable=False)
    target_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False
    )
    before_role: Mapped[str] = mapped_column(String(16), nullable=False)
    after_role: Mapped[str] = mapped_column(String(16), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)


class AdminAuditEvent(Base):
    """Generic, append-only evidence for an administrative command.

    Only server-computed field diffs belong here. Raw requests, provider bodies and
    arbitrary object payloads would turn the audit table into a sensitive-data bypass.
    """

    __tablename__ = "admin_audit_events"
    __table_args__ = (
        CheckConstraint("actor_identifier = btrim(actor_identifier) AND actor_identifier <> ''", name="ck_admin_audit_events_actor_identifier"),
        CheckConstraint("action = btrim(action) AND action <> ''", name="ck_admin_audit_events_action"),
        CheckConstraint("object_type = btrim(object_type) AND object_type <> ''", name="ck_admin_audit_events_object_type"),
        CheckConstraint("object_id = btrim(object_id) AND object_id <> ''", name="ck_admin_audit_events_object_id"),
        CheckConstraint("reason = btrim(reason) AND reason <> ''", name="ck_admin_audit_events_reason"),
        CheckConstraint("command_key = btrim(command_key) AND command_key <> ''", name="ck_admin_audit_events_command_key"),
        Index("ix_admin_audit_events_occurred_id", "occurred_at", "id"),
        Index("ix_admin_audit_events_action_occurred_id", "action", "occurred_at", "id"),
        Index("ix_admin_audit_events_object_occurred_id", "object_type", "object_id", "occurred_at", "id"),
        Index("ix_admin_audit_events_actor_occurred_id", "actor_identifier", "occurred_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    actor_identifier: Mapped[str] = mapped_column(String(320), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    object_type: Mapped[str] = mapped_column(String(80), nullable=False)
    object_id: Mapped[str] = mapped_column(String(160), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    before_diff: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    after_diff: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    related_version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    command_key: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
