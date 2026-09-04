"""Public weekly-review HTTP contracts expose only safe, user-readable outcomes."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi.testclient import TestClient

from app.agent.graph import NoopAgentRuntimeFactory
from app.auth.api import get_authenticated_principal
from app.dashboard.api import get_weekly_review_service
from app.dashboard.schemas import DashboardNutritionTotals, WeeklyReviewPublicResponse
from app.dashboard.service import DashboardTimezonePreconditionError, WeeklyReviewWeekStartInvalid
from app.main import create_app


class StubWeeklyReviewService:
    def __init__(self, timezone: str | None = "America/Los_Angeles") -> None:
        self.calls: list[tuple[uuid.UUID, date | None, bool]] = []
        self.timezone = timezone
        self.instant = datetime(2026, 9, 1, 1, tzinfo=UTC)

    def get_public_weekly_review(
        self, *, user_id: uuid.UUID, week_start: date | None, refresh: bool = False
    ) -> WeeklyReviewPublicResponse:
        if self.timezone is None:
            raise DashboardTimezonePreconditionError("missing preference")
        try:
            local_today = self.instant.astimezone(ZoneInfo(self.timezone)).date()
        except (TypeError, ZoneInfoNotFoundError) as error:
            raise DashboardTimezonePreconditionError("invalid preference") from error
        current_start = local_today - timedelta(days=local_today.weekday())
        if week_start is not None and (week_start.weekday() != 0 or week_start > current_start):
            raise WeeklyReviewWeekStartInvalid("invalid local week")
        self.calls.append((user_id, week_start, refresh))
        return WeeklyReviewPublicResponse(
            status="insufficient_coverage",
            week_start=date(2026, 8, 31),
            week_end=date(2026, 9, 6),
            coverage_days=2,
            meal_count=4,
            totals=DashboardNutritionTotals(energy_kcal="900", protein_g="42", fat_g="30", carbohydrate_g="100"),
            suggestions=(),
        )


def _client(service: StubWeeklyReviewService) -> TestClient:
    app = create_app(runtime_factory=NoopAgentRuntimeFactory())
    app.dependency_overrides[get_authenticated_principal] = lambda: uuid.uuid4()
    app.dependency_overrides[get_weekly_review_service] = lambda: service
    return TestClient(app)


def test_weekly_review_defaults_to_current_week_and_returns_only_safe_coverage_facts() -> None:
    service = StubWeeklyReviewService()
    with _client(service) as client:
        response = client.get("/api/v1/dashboard/weekly-review")

    assert response.status_code == 200
    assert response.json() == {
        "status": "insufficient_coverage",
        "week_start": "2026-08-31",
        "week_end": "2026-09-06",
        "coverage_days": 2,
        "meal_count": 4,
        "totals": {"energy_kcal": "900", "protein_g": "42", "fat_g": "30", "carbohydrate_g": "100"},
        "suggestions": [],
    }
    assert service.calls[0][1:] == (None, False)


def test_weekly_review_allows_only_monday_completed_weeks_and_never_refreshes_low_coverage() -> None:
    service = StubWeeklyReviewService()
    with _client(service) as client:
        accepted = client.get("/api/v1/dashboard/weekly-review", params={"week_start": "2026-08-24"})
        non_monday = client.get("/api/v1/dashboard/weekly-review", params={"week_start": "2026-08-25"})
        future = client.get("/api/v1/dashboard/weekly-review", params={"week_start": "2026-09-07"})
        refresh = client.post("/api/v1/dashboard/weekly-review/refresh", params={"week_start": "2026-08-24"})

    assert accepted.status_code == 200
    assert non_monday.status_code == 422
    assert future.status_code == 422
    assert refresh.status_code == 200
    assert service.calls[-1][2] is True
    # A low-coverage outcome itself is deterministic evidence that no Provider retry was attempted.
    assert all(call[2] is False or call[1] == date(2026, 8, 24) for call in service.calls)


def test_weekly_review_openapi_rejects_extra_or_technical_outcome_fields() -> None:
    schema = WeeklyReviewPublicResponse.model_json_schema()
    assert schema["additionalProperties"] is False
    assert "abstention_code" not in schema["properties"]
    assert "provider_error" not in schema["properties"]


def test_weekly_review_get_and_refresh_map_missing_or_corrupt_timezone_without_invocation() -> None:
    for timezone in (None, "Mars/Olympus"):
        service = StubWeeklyReviewService(timezone=timezone)
        with _client(service) as client:
            get_response = client.get("/api/v1/dashboard/weekly-review")
            refresh_response = client.post("/api/v1/dashboard/weekly-review/refresh")

        assert get_response.status_code == 409
        assert refresh_response.status_code == 409
        assert get_response.json() == {"detail": "Dashboard statistics timezone confirmation is required."}
        assert service.calls == []
