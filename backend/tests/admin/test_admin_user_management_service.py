from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.admin.service import AdminRoleChangeDenied, AdminService
from app.auth.models import User, UserRole

NOW = datetime(2026, 9, 8, tzinfo=UTC)


def user(role: UserRole, email: str) -> User:
    return User(id=uuid.uuid4(), email=email, password_hash="hash", role=role.value, is_active=True, email_verified_at=NOW, created_at=NOW, updated_at=NOW)


class Repo:
    def __init__(self, *users: User):
        self.users = {item.id: item for item in users}
        self.events = {}
        self.audits = []

    def get_user_by_id(self, user_id): return self.users.get(user_id)
    def get_user_for_update(self, user_id): return self.users.get(user_id)
    def acquire_bootstrap_lock(self): return None
    def count_active_admins(self): return sum(item.role == "admin" and item.is_active for item in self.users.values())
    def get_audit_event_by_command_key(self, key): return self.events.get(key)
    def add_audit(self, audit):
        self.audits.append(audit)
        return audit
    def add_audit_event(self, event):
        self.events[event.command_key] = event
        return event
    def count_users_by_role(self): return {role: sum(item.role == role for item in self.users.values()) for role in ("user", "admin")}
    def list_users(self, *, query, limit, offset):
        rows = [item for item in self.users.values() if (not query.role or item.role == query.role) and (not query.search or query.search in item.email)]
        return rows[offset:offset + limit], len(rows)


def test_demote_keeps_account_active_and_writes_single_audit_on_replay():
    actor, target = user(UserRole.ADMIN, "actor@example.test"), user(UserRole.ADMIN, "target@example.test")
    repo = Repo(actor, target)
    commits = []
    service = AdminService(repository=repo, now=lambda: NOW, commit=lambda: commits.append(True))
    first = service.change_user_role(actor_user_id=actor.id, target_user_id=target.id, after_role=UserRole.USER, reason="职责调整", command_key="role-command-0001")
    replay = service.change_user_role(actor_user_id=actor.id, target_user_id=target.id, after_role=UserRole.USER, reason="职责调整", command_key="role-command-0001")
    assert target.role == "user" and target.is_active is True
    assert first == replay
    assert len(repo.audits) == 1 and len(repo.events) == 1 and len(commits) == 1


def test_role_change_rejects_self():
    actor = user(UserRole.ADMIN, "actor@example.test")
    ordinary = user(UserRole.USER, "user@example.test")
    service = AdminService(repository=Repo(actor, ordinary), now=lambda: NOW)
    with pytest.raises(AdminRoleChangeDenied, match="own role"):
        service.change_user_role(actor_user_id=actor.id, target_user_id=actor.id, after_role=UserRole.USER, reason="测试", command_key="role-command-0002")

def test_promote_requires_verified_active_target():
    actor, target = user(UserRole.ADMIN, "actor@example.test"), user(UserRole.USER, "target@example.test")
    target.email_verified_at = None
    with pytest.raises(AdminRoleChangeDenied, match="active verified"):
        AdminService(repository=Repo(actor, target), now=lambda: NOW).change_user_role(actor_user_id=actor.id, target_user_id=target.id, after_role=UserRole.ADMIN, reason="新增管理员", command_key="role-command-0004")
