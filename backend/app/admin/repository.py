"""SQLAlchemy adapter for admin role reads, locks, and audit insertion."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, exists, or_, select, text
from sqlalchemy.orm import Session

from app.admin.models import AdminAuditEvent, AdminRoleAudit, CatalogDraft, CatalogDraftChangeSet, CatalogDraftRevision
from app.auth.models import User, UserRole


class SqlAlchemyAdminRepository:
    """Flush-only persistence adapter; the service owns the transaction boundary."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def acquire_bootstrap_lock(self) -> None:
        """Serialize the one-time bootstrap check without adding mutable global state."""

        self._session.execute(text("SELECT pg_advisory_xact_lock(918273645)"))

    def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        return self._session.get(User, user_id)

    def get_user_by_email(self, normalized_email: str) -> User | None:
        return self._session.scalar(select(User).where(User.email == normalized_email))

    def get_user_for_update(self, user_id: uuid.UUID) -> User | None:
        return self._session.scalar(
            select(User).where(User.id == user_id).with_for_update()
        )

    def has_active_admin(self) -> bool:
        return bool(
            self._session.scalar(
                select(
                    exists().where(
                        User.role == UserRole.ADMIN.value,
                        User.is_active.is_(True),
                    )
                )
            )
        )

    def add_audit(self, audit: AdminRoleAudit) -> AdminRoleAudit:
        self._session.add(audit)
        self._session.flush()
        return audit

    def add_audit_event(self, event: AdminAuditEvent) -> AdminAuditEvent:
        self._session.add(event)
        self._session.flush()
        return event

    def get_catalog_draft(self, draft_id: uuid.UUID) -> CatalogDraft | None:
        return self._session.get(CatalogDraft, draft_id)

    def get_catalog_draft_command(self, command_key: str) -> CatalogDraftChangeSet | None:
        return self._session.scalar(select(CatalogDraftChangeSet).where(CatalogDraftChangeSet.command_key == command_key))

    def add_catalog_draft(self, draft: CatalogDraft) -> CatalogDraft:
        self._session.add(draft)
        self._session.flush()
        return draft

    def add_catalog_draft_change_set(self, change_set: CatalogDraftChangeSet) -> CatalogDraftChangeSet:
        self._session.add(change_set)
        self._session.flush()
        return change_set

    def add_catalog_draft_revision(self, revision: CatalogDraftRevision) -> CatalogDraftRevision:
        self._session.add(revision)
        self._session.flush()
        return revision

    def list_audit_events(
        self,
        *,
        limit: int,
        cursor_position: tuple[datetime, uuid.UUID] | None,
        action: str | None = None,
        object_type: str | None = None,
        object_id: str | None = None,
        actor_identifier: str | None = None,
        reason: str | None = None,
        occurred_after: datetime | None = None,
        occurred_before: datetime | None = None,
    ) -> list[AdminAuditEvent]:
        """Read a deterministic keyset page without materializing any raw payload."""

        statement = select(AdminAuditEvent)
        if action is not None:
            statement = statement.where(AdminAuditEvent.action == action)
        if object_type is not None:
            statement = statement.where(AdminAuditEvent.object_type == object_type)
        if object_id is not None:
            statement = statement.where(AdminAuditEvent.object_id == object_id)
        if actor_identifier is not None:
            statement = statement.where(AdminAuditEvent.actor_identifier == actor_identifier)
        if reason is not None:
            statement = statement.where(AdminAuditEvent.reason.ilike(f"%{reason}%"))
        if occurred_after is not None:
            statement = statement.where(AdminAuditEvent.occurred_at >= occurred_after)
        if occurred_before is not None:
            statement = statement.where(AdminAuditEvent.occurred_at <= occurred_before)
        if cursor_position is not None:
            occurred_at, event_id = cursor_position
            statement = statement.where(
                or_(
                    AdminAuditEvent.occurred_at < occurred_at,
                    and_(AdminAuditEvent.occurred_at == occurred_at, AdminAuditEvent.id < event_id),
                )
            )
        return list(
            self._session.scalars(
                statement.order_by(AdminAuditEvent.occurred_at.desc(), AdminAuditEvent.id.desc()).limit(limit)
            )
        )
