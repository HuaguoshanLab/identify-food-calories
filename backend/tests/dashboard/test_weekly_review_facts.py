from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
import uuid

import pytest

from app.dashboard.repository import DashboardDailyAggregate
from app.dashboard.ports import DashboardTimezone
from app.dashboard.schemas import DashboardNutritionTotals
from app.dashboard.service import DashboardTimezonePreconditionError, WeeklyReviewService


class FactsRepository:
    def __init__(self, rows: list[DashboardDailyAggregate], timezone: str | None = "Asia/Shanghai") -> None:
        self.rows = rows
        self.timezone = timezone
        self.aggregate_calls: list[tuple[date, date]] = []

    def get_daily_aggregates(self, *, user_id: uuid.UUID, start_date: date, end_date: date):
        self.aggregate_calls.append((start_date, end_date))
        return [row for row in self.rows if start_date <= row.consumed_local_date <= end_date]

    def get_dashboard_timezone_for_user(self, *, user_id: uuid.UUID) -> DashboardTimezone | None:
        del user_id
        return DashboardTimezone(time_zone=self.timezone) if self.timezone is not None else None


def _aggregate(day: date, count: int = 1) -> DashboardDailyAggregate:
    return DashboardDailyAggregate(
        consumed_local_date=day, meal_count=count,
        totals=DashboardNutritionTotals(energy_kcal=Decimal("500"), protein_g=Decimal("30"), fat_g=Decimal("15"), carbohydrate_g=Decimal("40")),
    )


def test_facts_use_monday_and_return_deterministic_insufficient_coverage() -> None:
    provider_calls = 0

    def provider(_facts):
        nonlocal provider_calls
        provider_calls += 1
        return "should never run"

    service = WeeklyReviewService(
        repository=FactsRepository([_aggregate(date(2026, 8, 31), 2), _aggregate(date(2026, 9, 2), 2)]),
        cache_repository=object(), provider=provider, now=lambda: datetime(2026, 9, 3, 9, tzinfo=UTC),
    )
    review = service.get_weekly_review(user_id=uuid.uuid4())

    assert review.facts.week_start == date(2026, 8, 31)
    assert review.facts.coverage_days == 2
    assert review.facts.meal_count == 4
    assert review.abstention_code == "INSUFFICIENT_COVERAGE"
    assert provider_calls == 0


def test_weekly_facts_use_local_monday_across_dst_and_fail_closed_before_provider() -> None:
    instant = datetime(2026, 3, 9, 0, 30, tzinfo=UTC)
    shanghai_repository = FactsRepository([_aggregate(date(2026, 3, 9), 1)], "Asia/Shanghai")
    los_angeles_repository = FactsRepository([_aggregate(date(2026, 3, 8), 1)], "America/Los_Angeles")

    shanghai = WeeklyReviewService(
        repository=shanghai_repository, cache_repository=object(), provider=lambda _: "unused", now=lambda: instant
    ).get_weekly_review(user_id=uuid.uuid4())
    los_angeles = WeeklyReviewService(
        repository=los_angeles_repository, cache_repository=object(), provider=lambda _: "unused", now=lambda: instant
    ).get_weekly_review(user_id=uuid.uuid4())

    assert shanghai.facts.week_start == date(2026, 3, 9)
    assert los_angeles.facts.week_start == date(2026, 3, 2)

    for timezone in (None, "Mars/Olympus"):
        invalid = FactsRepository([], timezone)
        with pytest.raises(DashboardTimezonePreconditionError):
            WeeklyReviewService(repository=invalid, cache_repository=object(), provider=lambda _: "unused", now=lambda: instant).get_public_weekly_review(user_id=uuid.uuid4())
        assert invalid.aggregate_calls == []
