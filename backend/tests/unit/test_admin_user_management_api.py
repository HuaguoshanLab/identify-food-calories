from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.admin.api import get_admin_service
from app.admin.schemas import AdminRoleChangeResponse, AdminRoleListResponse, AdminUserPageResponse
from app.admin.service import AdminRoleChangeDenied
from app.agent.graph import NoopAgentRuntimeFactory
from app.auth.api import get_authenticated_principal
from app.main import create_app

NOW = datetime(2026, 9, 8, tzinfo=UTC)
TARGET = uuid.uuid4()


class Service:
    def list_users(self, **kwargs):
        assert kwargs["query"].search == "member@example.test"
        return AdminUserPageResponse(items=[{"id": TARGET, "email": "member@example.test", "email_verified_at": NOW, "is_active": True, "role": "user", "created_at": NOW, "updated_at": NOW}], total=1, page=1, page_size=20)

    def list_roles(self, **_kwargs):
        return AdminRoleListResponse(items=[{"role": "admin", "label": "管理员", "description": "后台权限", "account_count": 1, "permissions": ["管理管理员角色"]}])

    def change_user_role(self, **kwargs):
        assert kwargs["target_user_id"] == TARGET
        assert kwargs["reason"] == "承担后台职责"
        return AdminRoleChangeResponse(audit_id=uuid.uuid4(), target_user_id=TARGET, before_role="user", after_role="admin", occurred_at=NOW)


def client(service=Service()):
    app = create_app(runtime_factory=NoopAgentRuntimeFactory())
    app.dependency_overrides[get_authenticated_principal] = lambda: uuid.uuid4()
    app.dependency_overrides[get_admin_service] = lambda: service
    return TestClient(app)


def test_user_and_role_reads_return_only_allowlisted_fields():
    with client() as api:
        users = api.get("/api/v1/admin/users?search=member@example.test")
        roles = api.get("/api/v1/admin/roles")
    assert users.status_code == roles.status_code == 200
    assert set(users.json()["items"][0]) == {"id", "email", "email_verified_at", "is_active", "role", "created_at", "updated_at"}
    assert "password_hash" not in users.text and "sessions" not in users.text


def test_role_change_requires_reason_confirmation_and_idempotency_key():
    with client() as api:
        invalid = api.patch(f"/api/v1/admin/users/{TARGET}/role", json={"role": "admin", "reason": "", "confirm": True})
        changed = api.patch(f"/api/v1/admin/users/{TARGET}/role", headers={"Idempotency-Key": "role-command-key-0001"}, json={"role": "admin", "reason": "承担后台职责", "confirm": True})
    assert invalid.status_code == 422
    assert changed.status_code == 200 and changed.json()["after_role"] == "admin"


class ConflictService(Service):
    def change_user_role(self, **_kwargs):
        raise AdminRoleChangeDenied("the last active administrator cannot be demoted")


def test_role_policy_conflict_is_public_409():
    with client(ConflictService()) as api:
        response = api.patch(f"/api/v1/admin/users/{TARGET}/role", headers={"Idempotency-Key": "role-command-key-0002"}, json={"role": "user", "reason": "错误操作", "confirm": True})
    assert response.status_code == 409
    assert response.json()["detail"] == "the last active administrator cannot be demoted"
