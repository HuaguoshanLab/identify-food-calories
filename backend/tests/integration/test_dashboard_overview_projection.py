"""Dashboard overview consumes a completed-plan projection through its narrow port."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.agent.models import AgentRun, AgentThread
from app.auth.models import User, UserRole
from app.dashboard.ports import PlanningTargetEligibility
from app.dashboard.repository import SqlAlchemyDashboardRepository
from app.dashboard.service import DashboardService
from app.records.models import DashboardTimezonePreference, MealRecord


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
    now = datetime(2026, 9, 2, tzinfo=UTC)
    owner = User(id=uuid.uuid4(), email=f"dashboard-projection-{uuid.uuid4().hex}@example.test", password_hash="digest", role=UserRole.USER.value, is_active=True, email_verified_at=now, created_at=now, updated_at=now)
    thread = AgentThread(id=uuid.uuid4(), user_id=owner.id, status="completed", revision=1, created_at=now, last_activity_at=now, deleted_at=None)
    run = AgentRun(id=uuid.uuid4(), user_id=owner.id, thread_id=thread.id, command_key=f"dashboard-projection-run-{uuid.uuid4().hex}", command_hash="a" * 64, status="completed", graph_version="dashboard.v1", prompt_version="prompt.v1", tool_version="tools.v1", model_provider=None, model_version=None, graph_steps=1, model_calls=0, tool_calls=0, elapsed_ms=1, estimated_cost_usd=Decimal("0"), failure_code=None, created_at=now, updated_at=now, finished_at=now)
    other = User(id=uuid.uuid4(), email=f"dashboard-projection-other-{uuid.uuid4().hex}@example.test", password_hash="digest", role=UserRole.USER.value, is_active=True, email_verified_at=now, created_at=now, updated_at=now)
    db_session.add_all([owner, other])
    db_session.flush()
    db_session.add(thread)
    db_session.flush()
    db_session.add(run)
    db_session.flush()
    db_session.add_all([
        DashboardTimezonePreference(user_id=owner.id, time_zone="UTC", confirmed_at=now),
        DashboardTimezonePreference(user_id=other.id, time_zone="UTC", confirmed_at=now),
    ])
    db_session.add(
        MealRecord(
            id=uuid.uuid4(), user_id=owner.id, source_run_id=run.id, agent_thread_id=thread.id, agent_run_id=run.id,
            command_key=f"dashboard-projection-{uuid.uuid4().hex}", consumed_at=now, consumed_time_zone="UTC", consumed_local_date=date(2026, 9, 2),
            local_date_source="submitted_time_zone", nutrition_catalog_version="catalog.v1", calculation_version="calculation.v1",
            energy_kcal=Decimal("120"), protein_g=Decimal("10"), fat_g=Decimal("2"), carbohydrate_g=Decimal("20"),
            created_at=now, updated_at=now, deleted_at=None,
        )
    )
    db_session.flush()
    service = DashboardService(
        repository=SqlAlchemyDashboardRepository(db_session),
        target_port=FakePlanningPort(owner.id, PlanningTargetEligibility.unavailable()), now=lambda: now,
    )

    owner_overview = service.get_overview(user_id=owner.id)
    foreign_overview = service.get_overview(user_id=other.id)

    assert owner_overview.today.meal_count == 1
    assert owner_overview.target_eligibility.model_dump(exclude_none=True) == {"eligible": False}
    assert foreign_overview.today.meal_count == 0
    assert foreign_overview.target_eligibility.model_dump(exclude_none=True) == {"eligible": False}
