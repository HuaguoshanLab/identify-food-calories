"""HTTP contracts for dashboard routes without a database runtime."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient

from app.agent.graph import NoopAgentRuntimeFactory
from app.auth.api import get_authenticated_principal
from app.dashboard.api import get_dashboard_service
from app.dashboard.ports import DashboardTimezone, PlanningTargetEligibility
from app.dashboard.schemas import DashboardDaySummary, DashboardHistoryPage, DashboardNutritionTotals, DashboardOverview
from app.dashboard.service import DashboardService, InvalidDashboardCursor
from app.main import create_app


NOW = datetime(2026, 9, 2, 8, tzinfo=UTC)


def _day(day: date) -> DashboardDaySummary:
    return DashboardDaySummary(
        consumed_local_date=day,
        totals=DashboardNutritionTotals(energy_kcal=Decimal("100"), protein_g=Decimal("10"), fat_g=Decimal("5"), carbohydrate_g=Decimal("20")),
        meal_count=1,
    )


class StubDashboardService:
    def __init__(self) -> None:
        self.overview_calls: list[uuid.UUID] = []

    def get_overview(self, *, user_id: uuid.UUID) -> DashboardOverview:
        self.overview_calls.append(user_id)
        return DashboardOverview(today=_day(date(2026, 9, 2)), week=tuple(_day(date(2026, 8, 27) + timedelta(days=index)) for index in range(7)), target_eligibility=PlanningTargetEligibility.unavailable())

    def get_history(self, *, user_id: uuid.UUID, cursor: str | None, limit: int) -> DashboardHistoryPage:
        del user_id, limit
        if cursor is not None:
            raise InvalidDashboardCursor()
        return DashboardHistoryPage(groups=(), next_cursor=None)


class CountingDashboardRepository:
    def __init__(self, timezone: str | None) -> None:
        self.timezone = timezone
        self.aggregate_calls = 0

    def get_dashboard_timezone_for_user(self, *, user_id: uuid.UUID) -> DashboardTimezone | None:
        del user_id
        return DashboardTimezone(time_zone=self.timezone) if self.timezone is not None else None

    def get_daily_aggregates(self, *, user_id: uuid.UUID, start_date: date, end_date: date):
        del user_id, start_date, end_date
        self.aggregate_calls += 1
        return []

    def get_history_page(self, *, user_id: uuid.UUID, cursor, limit: int):
        del user_id, cursor, limit
        return []


class UnavailableTargetPort:
    def get_dashboard_target_eligibility(self, *, user_id: uuid.UUID) -> PlanningTargetEligibility:
        del user_id
        return PlanningTargetEligibility.unavailable()


def _client(service: StubDashboardService | None = None) -> TestClient:
    app = create_app(runtime_factory=NoopAgentRuntimeFactory())
    app.dependency_overrides[get_authenticated_principal] = lambda: uuid.uuid4()
    dashboard_service = service or StubDashboardService()
    app.dependency_overrides[get_dashboard_service] = lambda: dashboard_service
    return TestClient(app)


def test_dashboard_openapi_exposes_only_overview_and_history_and_omits_unavailable_targets() -> None:
    with _client() as client:
        response = client.get("/api/v1/dashboard/overview")
        openapi = client.app.openapi()
    assert response.status_code == 200
    assert response.json()["target_eligibility"] == {"eligible": False}
    assert set(openapi["paths"]["/api/v1/dashboard/overview"]) == {"get"}
    assert set(openapi["paths"]["/api/v1/dashboard/history"]) == {"get"}


def test_dashboard_overview_ignores_browser_selected_week_start() -> None:
    service = StubDashboardService()
    with _client(service) as client:
        response = client.get("/api/v1/dashboard/overview", params={"week_start": "2026-08-24"})

    assert response.status_code == 200
    assert len(service.overview_calls) == 1


def test_dashboard_rejects_tampered_cursor_and_invalid_page_range() -> None:
    with _client() as client:
        cursor = client.get("/api/v1/dashboard/history", params={"cursor": "not-a-dashboard-cursor"})
        range_error = client.get("/api/v1/dashboard/history", params={"limit": 0})
    assert cursor.status_code == 422
    assert range_error.status_code == 422


def test_dashboard_overview_maps_missing_or_corrupt_timezone_without_aggregate_or_leaks() -> None:
    for timezone in (None, "Mars/Olympus", "/invalid-timezone"):
        repository = CountingDashboardRepository(timezone)
        service = DashboardService(
            repository=repository,
            target_port=UnavailableTargetPort(),
            now=lambda: NOW,
        )
        app = create_app(runtime_factory=NoopAgentRuntimeFactory())
        app.dependency_overrides[get_authenticated_principal] = lambda: uuid.uuid4()
        app.dependency_overrides[get_dashboard_service] = lambda: service

        with TestClient(app) as client:
            response = client.get("/api/v1/dashboard/overview")

        assert response.status_code == 409
        assert response.json() == {"detail": "Dashboard statistics timezone confirmation is required."}
        assert repository.aggregate_calls == 0
        assert "Mars" not in response.text
        assert "repository" not in response.text.lower()
        assert "provider" not in response.text.lower()
        assert "state" not in response.text.lower()
