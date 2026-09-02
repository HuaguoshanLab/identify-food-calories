"""ORM state for immutable admin-role change evidence."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, Uuid
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


class CatalogDraft(Base):
    """Mutable working copy; released nutrition catalog rows remain immutable."""

    __tablename__ = "catalog_drafts"
    __table_args__ = (
        CheckConstraint("canonical_name = btrim(canonical_name) AND canonical_name <> ''", name="ck_catalog_drafts_name"),
        CheckConstraint("source_name = btrim(source_name) AND source_name <> ''", name="ck_catalog_drafts_source_name"),
        CheckConstraint("source_url LIKE 'https://%'", name="ck_catalog_drafts_source_url_https"),
        CheckConstraint("authorization_status IN ('authorized', 'pending', 'revoked')", name="ck_catalog_drafts_authorization"),
        CheckConstraint("revision > 0", name="ck_catalog_drafts_revision_positive"),
        CheckConstraint("energy_kcal_per_100g >= 0 AND protein_g_per_100g >= 0 AND fat_g_per_100g >= 0 AND carbohydrate_g_per_100g >= 0", name="ck_catalog_drafts_nutrients_nonnegative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    canonical_name: Mapped[str] = mapped_column(String(200), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    energy_kcal_per_100g: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    protein_g_per_100g: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    fat_g_per_100g: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    carbohydrate_g_per_100g: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    source_name: Mapped[str] = mapped_column(String(120), nullable=False)
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    authorization_status: Mapped[str] = mapped_column(String(16), nullable=False)
    revision: Mapped[int] = mapped_column(nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CatalogDraftChangeSet(Base):
    """Append-only server-computed mutation evidence and idempotency record."""

    __tablename__ = "catalog_draft_change_sets"
    __table_args__ = (
        CheckConstraint("actor_identifier = btrim(actor_identifier) AND actor_identifier <> ''", name="ck_catalog_draft_changes_actor"),
        CheckConstraint("reason = btrim(reason) AND reason <> ''", name="ck_catalog_draft_changes_reason"),
        CheckConstraint("command_key = btrim(command_key) AND command_key <> ''", name="ck_catalog_draft_changes_command"),
        CheckConstraint("revision_before >= 0 AND revision_after > revision_before", name="ck_catalog_draft_changes_revision"),
        UniqueConstraint("command_key", name="uq_catalog_draft_change_sets_command_key"),
        Index("ix_catalog_draft_change_sets_draft_revision", "draft_id", "revision_after"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    draft_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("catalog_drafts.id", ondelete="RESTRICT"), nullable=False)
    actor_identifier: Mapped[str] = mapped_column(String(320), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    command_key: Mapped[str] = mapped_column(String(160), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    revision_before: Mapped[int] = mapped_column(nullable=False)
    revision_after: Mapped[int] = mapped_column(nullable=False)
    before_diff: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    after_diff: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)


class CatalogDraftRevision(Base):
    """Immutable field snapshot for every mutable draft revision."""

    __tablename__ = "catalog_draft_revisions"
    __table_args__ = (
        CheckConstraint("revision > 0", name="ck_catalog_draft_revisions_positive"),
        UniqueConstraint("draft_id", "revision", name="uq_catalog_draft_revisions_draft_revision"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    draft_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("catalog_drafts.id", ondelete="RESTRICT"), nullable=False)
    change_set_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("catalog_draft_change_sets.id", ondelete="RESTRICT"), nullable=False)
    revision: Mapped[int] = mapped_column(nullable=False)
    snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
