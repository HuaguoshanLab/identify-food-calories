"""HTTPX-style contracts for minimum safe administrator run projections."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from app.admin.api import get_admin_service
from app.admin.schemas import AdminRunDetailResponse, AdminRunMetricsResponse, AdminRunPageResponse
from app.agent.graph import NoopAgentRuntimeFactory
from app.auth.api import get_authenticated_principal
from app.main import create_app


class StubRunService:
    def get_run_metrics(self, **_kwargs: object) -> AdminRunMetricsResponse:
        return AdminRunMetricsResponse(
            terminal_count=2, failure_ratio=Decimal("0.5"), p50_elapsed_ms=10,
            p95_elapsed_ms=20, total_cost_usd=Decimal("0.000200"),
            from_=datetime(2026, 9, 2, tzinfo=UTC), to=datetime(2026, 9, 3, tzinfo=UTC),
        )

    def list_agent_runs(self, **_kwargs: object) -> AdminRunPageResponse:
        return AdminRunPageResponse(
            items=[AdminRunDetailResponse(
                id=uuid.uuid4(), status="failed", graph_version="agent-v1",
                model_provider="deepseek", model_version="deepseek-v4-flash", graph_steps=2,
                model_calls=1, tool_calls=1, elapsed_ms=20, estimated_cost_usd=Decimal("0.000100"),
                failure_code="TIMEOUT", finished_at=datetime(2026, 9, 3, tzinfo=UTC),
            )],
            next_cursor=None,
        )

    def get_agent_run(self, **_kwargs: object) -> AdminRunDetailResponse:
        return self.list_agent_runs().items[0]


def _client() -> TestClient:
    app = create_app(runtime_factory=NoopAgentRuntimeFactory())
    app.dependency_overrides[get_authenticated_principal] = lambda: uuid.uuid4()
    app.dependency_overrides[get_admin_service] = StubRunService
    return TestClient(app)


def test_run_endpoints_return_only_allowlisted_ledger_fields() -> None:
    with _client() as client:
        metrics = client.get("/api/v1/admin/runs/metrics")
        listing = client.get("/api/v1/admin/runs?limit=1&status=failed")
        detail = client.get(f"/api/v1/admin/runs/{listing.json()['items'][0]['id']}")

    assert metrics.status_code == listing.status_code == detail.status_code == 200
    assert set(metrics.json()) == {"terminal_count", "failure_ratio", "p50_elapsed_ms", "p95_elapsed_ms", "total_cost_usd", "from", "to"}
    assert metrics.json()["from"] == "2026-09-02T00:00:00Z"
    assert metrics.json()["to"] == "2026-09-03T00:00:00Z"
    payload = detail.json()
    assert set(payload) == {
        "id", "status", "graph_version", "model_provider", "model_version", "graph_steps",
        "model_calls", "tool_calls", "elapsed_ms", "estimated_cost_usd", "failure_code", "finished_at", "invocations",
    }
    forbidden = {"email", "raw", "image", "body", "state", "reasoning", "key", "endpoint"}
    assert forbidden.isdisjoint(" ".join(payload).lower())


def test_run_endpoint_rejects_unbounded_or_invalid_filters() -> None:
    with _client() as client:
        response = client.get("/api/v1/admin/runs?limit=101&status=unknown")
    assert response.status_code == 422
