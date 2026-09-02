"""Real PostgreSQL contracts for generic append-only admin audit storage."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.admin.models import AdminAuditEvent
from app.admin.repository import SqlAlchemyAdminRepository


def test_repository_flushes_generic_audit_without_commit(db_session) -> None:
    event = AdminAuditEvent(
        id=uuid.uuid4(), actor_identifier="admin-id", occurred_at=datetime.now(UTC),
        action="catalog.publish", object_type="catalog_version", object_id="catalog-v1",
        reason="approved", before_diff={"status": "review"}, after_diff={"status": "published"},
        related_version="catalog-v1", command_key="publish-00000001",
    )
    repository = SqlAlchemyAdminRepository(db_session)
    repository.add_audit_event(event)
    assert db_session.scalar(select(AdminAuditEvent).where(AdminAuditEvent.id == event.id)) == event
