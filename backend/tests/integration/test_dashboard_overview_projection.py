"""Dashboard overview consumes a completed-plan projection through its narrow port."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.dashboard.ports import PlanningTargetEligibility
from app.dashboard.repository import SqlAlchemyDashboardRepository
from app.dashboard.service import DashboardService
from app.records.models import MealRecord


pytestmark = pytest.mark.skipif(
    __import__("os").environ.get("APP_ENV") != "test",
    reason="requires the guarded PostgreSQL test environment",
)


class FakePlanningPort:
    def __init__(self, owner: uuid.UUID, value: PlanningTargetEligibility) -> None:
        self.owner = owner
        self.value = value

    def get_dashboard_target_eligibility(self, *, user_id: uuid.UUID) -> PlanningTargetEligibility:
        return self.value if user_id == self.owner else PlanningTargetEligibility.unavailable()


def test_overview_omits_targets_when_the_injected_projection_port_revokes_or_is_foreign(db_session) -> None:
    owner, other = uuid.uuid4(), uuid.uuid4()
    now = datetime(2026, 9, 2, tzinfo=UTC)
    db_session.add(
        MealRecord(
            id=uuid.uuid4(), user_id=owner, source_run_id=uuid.uuid4(), agent_thread_id=uuid.uuid4(), agent_run_id=uuid.uuid4(),
            command_key=f"dashboard-projection-{uuid.uuid4().hex}", consumed_at=now, consumed_time_zone="UTC", consumed_local_date=date(2026, 9, 2),
            local_date_source="submitted_time_zone", nutrition_catalog_version="catalog.v1", calculation_version="calculation.v1",
            energy_kcal=Decimal("120"), protein_g=Decimal("10"), fat_g=Decimal("2"), carbohydrate_g=Decimal("20"),
            created_at=now, updated_at=now, deleted_at=None,
        )
    )
    db_session.flush()
    service = DashboardService(
        repository=SqlAlchemyDashboardRepository(db_session),
        target_port=FakePlanningPort(owner, PlanningTargetEligibility.unavailable()), now=lambda: now,
    )

    owner_overview = service.get_overview(user_id=owner, week_start=date(2026, 8, 31))
    foreign_overview = service.get_overview(user_id=other, week_start=date(2026, 8, 31))

    assert owner_overview.today.meal_count == 1
    assert owner_overview.target_eligibility.model_dump(exclude_none=True) == {"eligible": False}
    assert foreign_overview.today.meal_count == 0
    assert foreign_overview.target_eligibility.model_dump(exclude_none=True) == {"eligible": False}
