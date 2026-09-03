"""HTTPX-style dependency contracts for admin RBAC endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from app.admin.api import get_admin_service
from app.admin.schemas import RuntimeConfigResponse
from app.admin.service import AdminPermissionDenied
from app.auth.api import get_authenticated_principal
from app.agent.graph import NoopAgentRuntimeFactory
from app.main import create_app


class DeniedAdminService:
    def require_role(self, **_kwargs: object) -> None:
        raise AdminPermissionDenied()

    def read_runtime_config(self, **_kwargs: object) -> None:
        raise AdminPermissionDenied()


class RuntimeConfigReadService:
    def read_runtime_config(self, **_kwargs: object) -> RuntimeConfigResponse:
        return RuntimeConfigResponse(
            id=uuid.uuid4(), version=2, provider="deepseek", model_alias="deepseek-v4-flash", enabled=True,
            single_call_cap_usd=Decimal("0.02"), period_cap_usd=Decimal("12"),
            input_usd_per_m=Decimal("0.14"), output_usd_per_m=Decimal("0.28"),
            created_at=datetime(2026, 9, 3, tzinfo=UTC),
        )


def test_current_database_role_denial_is_403_even_for_authenticated_principal() -> None:
    app = create_app(runtime_factory=NoopAgentRuntimeFactory())
    app.dependency_overrides[get_authenticated_principal] = lambda: uuid.uuid4()
    app.dependency_overrides[get_admin_service] = DeniedAdminService
    with TestClient(app) as client:
        response = client.get("/api/v1/admin/probe")
    assert response.status_code == 403


def test_runtime_config_read_is_rbac_protected_and_only_returns_allowlisted_projection() -> None:
    app = create_app(runtime_factory=NoopAgentRuntimeFactory())
    app.dependency_overrides[get_authenticated_principal] = lambda: uuid.uuid4()
    app.dependency_overrides[get_admin_service] = RuntimeConfigReadService
    with TestClient(app) as client:
        response = client.get("/api/v1/admin/runtime-config")
    assert response.status_code == 200
    assert set(response.json()) == {
        "id", "version", "provider", "model_alias", "enabled", "single_call_cap_usd", "period_cap_usd",
        "input_usd_per_m", "output_usd_per_m", "created_at",
    }
