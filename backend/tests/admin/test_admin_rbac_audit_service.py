"""RED contracts for database-authoritative admin command auditing."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.admin.models import AdminAuditEvent
from app.admin.service import AdminPermissionDenied, AdminService
from app.auth.models import User, UserRole


NOW = datetime(2026, 9, 2, tzinfo=UTC)


def _user(*, role: str, active: bool = True) -> User:
    return User(
        id=uuid.uuid4(), email="admin-test@example.com", password_hash="hash", role=role,
        is_active=active, email_verified_at=NOW, created_at=NOW, updated_at=NOW,
    )


class FakeAdminRepository:
    def __init__(self, user: User | None) -> None:
        self.user = user
        self.events: list[AdminAuditEvent] = []
        self.lookups: list[uuid.UUID] = []

    def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        self.lookups.append(user_id)
        return self.user if self.user is not None and self.user.id == user_id else None

    def add_audit_event(self, event: AdminAuditEvent) -> AdminAuditEvent:
        self.events.append(event)
        return event


def test_require_role_uses_current_active_database_user_not_claim() -> None:
    downgraded = _user(role=UserRole.USER.value)
    repository = FakeAdminRepository(downgraded)
    service = AdminService(repository=repository)

    with pytest.raises(AdminPermissionDenied):
        service.require_role(user_id=downgraded.id, required_role=UserRole.ADMIN)

    assert repository.lookups == [downgraded.id]


def test_record_command_audit_requires_reason_and_rolls_back_together() -> None:
    admin = _user(role=UserRole.ADMIN.value)
    repository = FakeAdminRepository(admin)
    rollbacks: list[bool] = []
    service = AdminService(
        repository=repository,
        now=lambda: NOW,
        commit=lambda: (_ for _ in ()).throw(RuntimeError("database failure")),
        rollback=lambda: rollbacks.append(True),
    )

    with pytest.raises(RuntimeError):
        service.record_command_audit(
            actor_user_id=admin.id,
            action="catalog.publish",
            object_type="catalog_version",
            object_id="catalog-v1",
            reason="approved release",
            before={"status": "review"},
            after={"status": "published"},
            related_version="catalog-v1",
            command_key="publish-00000001",
        )

    assert len(repository.events) == 1
    assert rollbacks == [True]


def test_command_audit_rejects_sensitive_or_nested_diffs_before_persistence() -> None:
    admin = _user(role=UserRole.ADMIN.value)
    repository = FakeAdminRepository(admin)
    service = AdminService(repository=repository, now=lambda: NOW)

    with pytest.raises(ValueError):
        service.record_command_audit(
            actor_user_id=admin.id, action="catalog.publish", object_type="catalog_version",
            object_id="catalog-v1", reason="approved", before={"email": "not-allowed"},
            after={"status": "published"}, related_version="catalog-v1", command_key="publish-00000002",
        )

    assert repository.events == []
