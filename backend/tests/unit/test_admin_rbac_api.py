"""HTTPX-style dependency contracts for admin RBAC endpoints."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.admin.api import get_admin_service
from app.admin.service import AdminPermissionDenied
from app.auth.api import get_authenticated_principal
from app.agent.graph import NoopAgentRuntimeFactory
from app.main import create_app


class DeniedAdminService:
    def require_role(self, **_kwargs: object) -> None:
        raise AdminPermissionDenied()


def test_current_database_role_denial_is_403_even_for_authenticated_principal() -> None:
    app = create_app(runtime_factory=NoopAgentRuntimeFactory())
    app.dependency_overrides[get_authenticated_principal] = lambda: uuid.uuid4()
    app.dependency_overrides[get_admin_service] = DeniedAdminService
    with TestClient(app) as client:
        response = client.get("/api/v1/admin/probe")
    assert response.status_code == 403
