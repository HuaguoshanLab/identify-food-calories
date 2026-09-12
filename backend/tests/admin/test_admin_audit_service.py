"""RED contracts for minimal audit projections and opaque cursor paging."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from app.admin.models import AdminAuditEvent
from app.admin.service import AdminService


NOW = datetime(2026, 9, 2, tzinfo=UTC)


class FakeAuditRepository:
    def __init__(self) -> None:
        self.actor_id = uuid.uuid4()
        self.last_list_filters: dict[str, object] = {}
        self.events = [
            AdminAuditEvent(
                id=uuid.uuid4(), actor_identifier=str(self.actor_id), occurred_at=NOW,
                action="catalog.publish", object_type="catalog_version", object_id="catalog-v1",
                reason="approved", before_diff={"status": "review"}, after_diff={"status": "published"},
                related_version="catalog-v1", command_key="publish-00000001",
            ),
            AdminAuditEvent(
                id=uuid.uuid4(), actor_identifier=str(self.actor_id), occurred_at=NOW,
                action="catalog.publish", object_type="catalog_version", object_id="catalog-v2",
                reason="approved", before_diff={"status": "review"}, after_diff={"status": "published"},
                related_version="catalog-v2", command_key="publish-00000002",
            ),
        ]

    def list_audit_events(self, **kwargs: object) -> list[AdminAuditEvent]:
        self.last_list_filters = kwargs
        return self.events

    def get_user_by_id(self, user_id: uuid.UUID) -> SimpleNamespace | None:
        return SimpleNamespace(email="admin@example.test") if user_id == self.actor_id else None

    def get_user_by_email(self, normalized_email: str) -> SimpleNamespace | None:
        return SimpleNamespace(id=self.actor_id) if normalized_email == "admin@example.test" else None


def test_audit_read_projects_only_allowlisted_fields_and_stable_cursor() -> None:
    service = AdminService(repository=FakeAuditRepository(), cursor_secret="test-secret")
    page = service.list_audit_events(limit=1, cursor=None, action="catalog.publish")

    item = page.items[0]
    assert item.action == "catalog.publish"
    assert item.actor_label == "admin@example.test"
    assert item.before == {"status": "review"}
    assert item.after == {"status": "published"}
    assert set(item.model_dump()) == {
        "id", "actor_identifier", "actor_label", "occurred_at", "action", "object_type", "object_id",
        "reason", "before", "after", "related_version", "command_key",
    }
    assert page.next_cursor is not None


def test_audit_actor_filter_accepts_administrator_email() -> None:
    repository = FakeAuditRepository()
    service = AdminService(repository=repository, cursor_secret="test-secret")

    service.list_audit_events(limit=1, cursor=None, actor="admin@example.test")

    assert repository.last_list_filters["actor_identifier"] == str(repository.actor_id)
