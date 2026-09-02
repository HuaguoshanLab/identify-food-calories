"""HTTP contract for readonly admin audit endpoint."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.admin.api import get_admin_service
from app.admin.schemas import AdminAuditEventResponse, AdminAuditPageResponse
from app.auth.api import get_authenticated_principal
from app.agent.graph import NoopAgentRuntimeFactory
from app.main import create_app


class StubAuditService:
    def require_role(self, **_kwargs: object) -> None:
        return None

    def list_audit_events(self, **_kwargs: object) -> AdminAuditPageResponse:
        return AdminAuditPageResponse(
            items=[AdminAuditEventResponse(
                id=uuid.uuid4(), actor_identifier="admin-id", occurred_at=datetime(2026, 9, 2, tzinfo=UTC),
                action="catalog.publish", object_type="catalog_version", object_id="catalog-v1",
                reason="approved", before={"status": "review"}, after={"status": "published"},
                related_version="catalog-v1", command_key="publish-00000001",
            )],
            next_cursor=None,
        )


def test_audit_endpoint_requires_current_role_and_returns_minimal_projection() -> None:
    app = create_app(runtime_factory=NoopAgentRuntimeFactory())
    app.dependency_overrides[get_authenticated_principal] = lambda: uuid.uuid4()
    app.dependency_overrides[get_admin_service] = StubAuditService
    with TestClient(app) as client:
        response = client.get("/api/v1/admin/audit?limit=1&action=catalog.publish&actor=admin-id")
    assert response.status_code == 200
    assert set(response.json()["items"][0]) == {
        "id", "actor_identifier", "occurred_at", "action", "object_type", "object_id",
        "reason", "before", "after", "related_version", "command_key",
    }
