"""HTTP contracts for dashboard routes without a database runtime."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient

from app.agent.graph import NoopAgentRuntimeFactory
from app.auth.api import get_authenticated_principal
from app.dashboard.api import get_dashboard_service
from app.dashboard.ports import PlanningTargetEligibility
from app.dashboard.schemas import DashboardDaySummary, DashboardHistoryPage, DashboardNutritionTotals, DashboardOverview
from app.main import create_app


NOW = datetime(2026, 9, 2, 8, tzinfo=UTC)


def _day(day: date) -> DashboardDaySummary:
    return DashboardDaySummary(
        consumed_local_date=day,
        totals=DashboardNutritionTotals(energy_kcal=Decimal("100"), protein_g=Decimal("10"), fat_g=Decimal("5"), carbohydrate_g=Decimal("20")),
        meal_count=1,
    )


class StubDashboardService:
    def get_overview(self, *, user_id: uuid.UUID, week_start: date | None = None) -> DashboardOverview:
        del user_id, week_start
        return DashboardOverview(today=_day(date(2026, 9, 2)), week=tuple(_day(date(2026, 8, 27) + timedelta(days=index)) for index in range(7)), target_eligibility=PlanningTargetEligibility.unavailable())

    def get_history(self, *, user_id: uuid.UUID, cursor: str | None, limit: int) -> DashboardHistoryPage:
        del user_id, cursor, limit
        return DashboardHistoryPage(groups=(), next_cursor=None)


def _client() -> TestClient:
    app = create_app(runtime_factory=NoopAgentRuntimeFactory())
    app.dependency_overrides[get_authenticated_principal] = lambda: uuid.uuid4()
    app.dependency_overrides[get_dashboard_service] = StubDashboardService
    return TestClient(app)


def test_dashboard_openapi_exposes_only_overview_and_history_and_omits_unavailable_targets() -> None:
    with _client() as client:
        response = client.get("/api/v1/dashboard/overview")
        openapi = client.app.openapi()
    assert response.status_code == 200
    assert response.json()["target_eligibility"] == {"eligible": False}
    assert set(openapi["paths"]["/api/v1/dashboard/overview"]) == {"get"}
    assert set(openapi["paths"]["/api/v1/dashboard/history"]) == {"get"}


def test_dashboard_rejects_tampered_cursor_and_invalid_page_range() -> None:
    with _client() as client:
        cursor = client.get("/api/v1/dashboard/history", params={"cursor": "not-a-dashboard-cursor"})
        range_error = client.get("/api/v1/dashboard/history", params={"limit": 0})
    assert cursor.status_code == 422
    assert range_error.status_code == 422
