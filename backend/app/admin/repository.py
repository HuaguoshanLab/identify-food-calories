"""SQLAlchemy adapter for admin role reads, locks, and audit insertion."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, exists, or_, select, text
from sqlalchemy.orm import Session

from app.admin.models import AdminAuditEvent, AdminRoleAudit, CatalogActivePublication, CatalogDraft, CatalogDraftChangeSet, CatalogDraftReview, CatalogDraftRevision, CatalogPublication, CatalogPublicationEligibility
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

    def get_catalog_draft(self, draft_id: uuid.UUID, *, for_update: bool = False) -> CatalogDraft | None:
        statement = select(CatalogDraft).where(CatalogDraft.id == draft_id)
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

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

    def acquire_catalog_publication_lock(self, draft_id: uuid.UUID) -> None:
        # Transaction-scoped advisory locking serializes publication even before a
        # pointer row exists, closing the first-publish race without global locks.
        self._session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:draft_id))"), {"draft_id": str(draft_id)})

    def get_catalog_review(self, *, draft_id: uuid.UUID, revision: int) -> CatalogDraftReview | None:
        return self._session.scalar(select(CatalogDraftReview).where(CatalogDraftReview.draft_id == draft_id, CatalogDraftReview.draft_revision == revision))

    def add_catalog_review(self, review: CatalogDraftReview) -> CatalogDraftReview:
        self._session.add(review)
        self._session.flush()
        return review

    def get_catalog_publication_command(self, command_key: str) -> CatalogPublication | None:
        return self._session.scalar(select(CatalogPublication).where(CatalogPublication.command_key == command_key))

    def add_catalog_publication(self, publication: CatalogPublication) -> CatalogPublication:
        self._session.add(publication)
        self._session.flush()
        return publication

    def get_active_catalog_publication(self, draft_id: uuid.UUID) -> CatalogPublication | None:
        return self._session.scalar(select(CatalogPublication).join(CatalogActivePublication, CatalogActivePublication.publication_id == CatalogPublication.id).where(CatalogActivePublication.draft_id == draft_id))

    def advance_active_catalog_publication(self, *, draft_id: uuid.UUID, publication_id: uuid.UUID) -> CatalogActivePublication:
        pointer = self._session.get(CatalogActivePublication, draft_id)
        if pointer is None:
            pointer = CatalogActivePublication(draft_id=draft_id, publication_id=publication_id, advanced_at=datetime.now().astimezone())
            self._session.add(pointer)
        else:
            pointer.publication_id = publication_id
            pointer.advanced_at = datetime.now().astimezone()
        self._session.flush()
        return pointer

    def get_catalog_publication(self, publication_id: uuid.UUID) -> CatalogPublication | None:
        return self._session.get(CatalogPublication, publication_id)

    def get_catalog_eligibility_command(self, command_key: str) -> CatalogPublicationEligibility | None:
        return self._session.scalar(select(CatalogPublicationEligibility).where(CatalogPublicationEligibility.command_key == command_key))

    def get_latest_catalog_eligibility(self, publication_id: uuid.UUID) -> CatalogPublicationEligibility | None:
        return self._session.scalar(
            select(CatalogPublicationEligibility)
            .where(CatalogPublicationEligibility.publication_id == publication_id)
            .order_by(CatalogPublicationEligibility.occurred_at.desc(), CatalogPublicationEligibility.id.desc())
            .limit(1)
        )

    def add_catalog_eligibility(self, eligibility: CatalogPublicationEligibility) -> CatalogPublicationEligibility:
        self._session.add(eligibility)
        self._session.flush()
        return eligibility

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
