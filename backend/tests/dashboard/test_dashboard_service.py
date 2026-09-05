"""Service contracts for dashboard facts and projection-backed targets."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from app.dashboard.ports import DashboardTimezone, PlanningTargetEligibility
from app.dashboard.schemas import DashboardHistoryCursor, DashboardNutritionTotals
from app.dashboard.service import DashboardService, DashboardTimezonePreconditionError


NOW = datetime(2026, 9, 2, 8, tzinfo=UTC)


class FakeDashboardRepository:
    def __init__(self, rows: list[object], timezone: str | None = "Asia/Shanghai") -> None:
        self.rows = rows
        self.timezone = timezone
        self.history_calls: list[tuple[uuid.UUID, DashboardHistoryCursor | None, int]] = []
        self.aggregate_calls: list[tuple[uuid.UUID, date, date]] = []

    def get_daily_aggregates(self, *, user_id: uuid.UUID, start_date: date, end_date: date) -> list[object]:
        self.aggregate_calls.append((user_id, start_date, end_date))
        return [row for row in self.rows if start_date <= row.consumed_local_date <= end_date]

    def get_dashboard_timezone_for_user(self, *, user_id: uuid.UUID) -> DashboardTimezone | None:
        del user_id
        return DashboardTimezone(time_zone=self.timezone) if self.timezone is not None else None

    def get_history_page(
        self, *, user_id: uuid.UUID, cursor: DashboardHistoryCursor | None, limit: int
    ) -> list[object]:
        self.history_calls.append((user_id, cursor, limit))
        return self.rows[:limit]


class FakeTargetPort:
    def __init__(self, eligibility: PlanningTargetEligibility) -> None:
        self.eligibility = eligibility
        self.calls: list[uuid.UUID] = []

    def get_dashboard_target_eligibility(self, *, user_id: uuid.UUID) -> PlanningTargetEligibility:
        self.calls.append(user_id)
        return self.eligibility


def _row(*, day: date, energy: str, count: int = 1) -> object:
    return type(
        "Aggregate",
        (),
        {
            "consumed_local_date": day,
            "totals": DashboardNutritionTotals(
                energy_kcal=Decimal(energy), protein_g=Decimal("20"), fat_g=Decimal("10"), carbohydrate_g=Decimal("30")
            ),
            "energy_kcal": Decimal(energy),
            "protein_g": Decimal("20"),
            "fat_g": Decimal("10"),
            "carbohydrate_g": Decimal("30"),
            "meal_count": count,
            "consumed_at": NOW,
            "id": uuid.uuid4(),
        },
    )()


def test_overview_has_seven_local_days_and_reads_targets_only_from_the_narrow_projection_port() -> None:
    user_id = uuid.uuid4()
    repository = FakeDashboardRepository([_row(day=date(2026, 9, 2), energy="456.50", count=2)])
    target_port = FakeTargetPort(PlanningTargetEligibility.unavailable())

    overview = DashboardService(
        repository=repository, target_port=target_port, now=lambda: NOW
    ).get_overview(user_id=user_id)

    assert overview.today.totals.energy_kcal == Decimal("456.50")
    assert overview.today.meal_count == 2
    assert [day.consumed_local_date for day in overview.week] == [date(2026, 8, 31) + timedelta(days=index) for index in range(7)]
    assert overview.target_eligibility.eligible is False
    assert overview.target_eligibility.target is None
    assert target_port.calls == [user_id]


def test_overview_has_no_caller_selected_week_and_uses_the_confirmed_local_current_week() -> None:
    user_id = uuid.uuid4()
    repository = FakeDashboardRepository([], "America/Los_Angeles")
    service = DashboardService(
        repository=repository,
        target_port=FakeTargetPort(PlanningTargetEligibility.unavailable()),
        now=lambda: datetime(2026, 3, 9, 0, 30, tzinfo=UTC),
    )

    overview = service.get_overview(user_id=user_id)

    assert overview.today.consumed_local_date == date(2026, 3, 8)
    assert [day.consumed_local_date for day in overview.week] == [
        date(2026, 3, 2) + timedelta(days=index) for index in range(7)
    ]
    assert repository.aggregate_calls == [(user_id, date(2026, 3, 2), date(2026, 3, 8))]


def test_history_keeps_server_cursor_opaque_and_groups_only_persisted_local_days() -> None:
    user_id = uuid.uuid4()
    rows = [_row(day=date(2026, 9, 2), energy="10"), _row(day=date(2026, 9, 1), energy="20")]
    repository = FakeDashboardRepository(rows)
    service = DashboardService(repository=repository, target_port=FakeTargetPort(PlanningTargetEligibility.unavailable()), now=lambda: NOW)

    page = service.get_history(user_id=user_id, cursor=None, limit=1)

    assert page.groups[0].consumed_local_date == date(2026, 9, 2)
    assert page.groups[0].totals.energy_kcal == Decimal("10")
    assert page.next_cursor is not None and "{" not in page.next_cursor
    assert repository.history_calls[0][2] == 2


def test_overview_uses_each_confirmed_iana_zone_at_one_utc_instant() -> None:
    instant = datetime(2026, 3, 9, 0, 30, tzinfo=UTC)
    target_port = FakeTargetPort(PlanningTargetEligibility.unavailable())
    shanghai = DashboardService(
        repository=FakeDashboardRepository([_row(day=date(2026, 3, 9), energy="100")], "Asia/Shanghai"),
        target_port=target_port,
        now=lambda: instant,
    ).get_overview(user_id=uuid.uuid4())
    los_angeles = DashboardService(
        repository=FakeDashboardRepository([_row(day=date(2026, 3, 8), energy="100")], "America/Los_Angeles"),
        target_port=target_port,
        now=lambda: instant,
    ).get_overview(user_id=uuid.uuid4())

    assert shanghai.today.consumed_local_date == date(2026, 3, 9)
    assert shanghai.week[0].consumed_local_date == date(2026, 3, 9)
    assert los_angeles.today.consumed_local_date == date(2026, 3, 8)
    assert los_angeles.week[0].consumed_local_date == date(2026, 3, 2)


@pytest.mark.parametrize("timezone", [None, "Mars/Olympus", "/invalid-timezone"])
def test_overview_fails_closed_before_queries_for_missing_or_invalid_timezone(timezone: str | None) -> None:
    repository = FakeDashboardRepository([], timezone)
    target_port = FakeTargetPort(PlanningTargetEligibility.unavailable())

    with pytest.raises(DashboardTimezonePreconditionError):
        DashboardService(repository=repository, target_port=target_port, now=lambda: NOW).get_overview(user_id=uuid.uuid4())

    assert repository.aggregate_calls == []
    assert target_port.calls == []
