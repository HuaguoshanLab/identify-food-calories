"""Real PostgreSQL proof for dashboard aggregation and keyset pagination."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from app.agent.models import AgentRun, AgentThread
from app.auth.models import User, UserRole
from app.dashboard.repository import SqlAlchemyDashboardRepository
from app.dashboard.schemas import DashboardHistoryCursor
from app.records.models import MealRecord


pytestmark = pytest.mark.skipif(
    __import__("os").environ.get("APP_ENV") != "test",
    reason="requires the guarded PostgreSQL test environment",
)


def _identity(db_session, *, label: str, now: datetime) -> tuple[User, AgentThread, AgentRun]:
    user = User(id=uuid.uuid4(), email=f"dashboard-{label}-{uuid.uuid4().hex}@example.test", password_hash="digest", role=UserRole.USER.value, is_active=True, email_verified_at=now, created_at=now, updated_at=now)
    thread = AgentThread(id=uuid.uuid4(), user_id=user.id, status="completed", revision=1, created_at=now, last_activity_at=now, deleted_at=None)
    run = AgentRun(id=uuid.uuid4(), user_id=user.id, thread_id=thread.id, command_key=f"dashboard-run-{uuid.uuid4().hex}", command_hash="a" * 64, status="completed", graph_version="dashboard.v1", prompt_version="prompt.v1", tool_version="tools.v1", model_provider=None, model_version=None, graph_steps=1, model_calls=0, tool_calls=0, elapsed_ms=1, estimated_cost_usd=Decimal("0"), failure_code=None, created_at=now, updated_at=now, finished_at=now)
    db_session.add(user)
    db_session.flush()
    db_session.add(thread)
    db_session.flush()
    db_session.add(run)
    db_session.flush()
    return user, thread, run


def _additional_run(db_session, *, user: User, thread: AgentThread, now: datetime) -> AgentRun:
    run = AgentRun(id=uuid.uuid4(), user_id=user.id, thread_id=thread.id, command_key=f"dashboard-run-{uuid.uuid4().hex}", command_hash="b" * 64, status="completed", graph_version="dashboard.v1", prompt_version="prompt.v1", tool_version="tools.v1", model_provider=None, model_version=None, graph_steps=1, model_calls=0, tool_calls=0, elapsed_ms=1, estimated_cost_usd=Decimal("0"), failure_code=None, created_at=now, updated_at=now, finished_at=now)
    db_session.add(run)
    db_session.flush()
    return run


def _record(*, user_id: uuid.UUID, thread_id: uuid.UUID, run_id: uuid.UUID, day: date, at: datetime, deleted_at: datetime | None = None) -> MealRecord:
    return MealRecord(
        id=uuid.uuid4(), user_id=user_id, source_run_id=run_id, agent_thread_id=thread_id, agent_run_id=run_id,
        command_key=f"dashboard-{uuid.uuid4().hex}", consumed_at=at, consumed_time_zone="UTC", consumed_local_date=day,
        local_date_source="submitted_time_zone", nutrition_catalog_version="catalog.v1", calculation_version="calculation.v1",
        energy_kcal=Decimal("100.25"), protein_g=Decimal("10.5"), fat_g=Decimal("5.25"), carbohydrate_g=Decimal("20.75"),
        created_at=at, updated_at=at, deleted_at=deleted_at,
    )


def test_daily_aggregates_are_tenant_filtered_and_exclude_soft_deleted_rows(db_session) -> None:
    now = datetime(2026, 9, 2, 12, tzinfo=UTC)
    owner, owner_thread, owner_run = _identity(db_session, label="owner", now=now)
    other, other_thread, other_run = _identity(db_session, label="other", now=now)
    owner_deleted_run = _additional_run(db_session, user=owner, thread=owner_thread, now=now)
    db_session.add_all([
        _record(user_id=owner.id, thread_id=owner_thread.id, run_id=owner_run.id, day=date(2026, 9, 2), at=now),
        _record(user_id=owner.id, thread_id=owner_thread.id, run_id=owner_deleted_run.id, day=date(2026, 9, 2), at=now - timedelta(hours=1), deleted_at=now),
        _record(user_id=other.id, thread_id=other_thread.id, run_id=other_run.id, day=date(2026, 9, 2), at=now),
    ])
    db_session.flush()

    aggregates = SqlAlchemyDashboardRepository(db_session).get_daily_aggregates(
        user_id=owner.id, start_date=date(2026, 9, 1), end_date=date(2026, 9, 7)
    )

    assert len(aggregates) == 1
    assert aggregates[0].consumed_local_date == date(2026, 9, 2)
    assert aggregates[0].meal_count == 1
    assert aggregates[0].totals.energy_kcal == Decimal("100.250000")


def test_history_keyset_uses_date_timestamp_and_id_without_leaks_or_duplicates(db_session) -> None:
    timestamp = datetime(2026, 9, 2, 12, tzinfo=UTC)
    owner, owner_thread, owner_run = _identity(db_session, label="owner", now=timestamp)
    other, other_thread, other_run = _identity(db_session, label="other", now=timestamp)
    owner_second_run = _additional_run(db_session, user=owner, thread=owner_thread, now=timestamp)
    first = _record(user_id=owner.id, thread_id=owner_thread.id, run_id=owner_run.id, day=date(2026, 9, 2), at=timestamp)
    second = _record(user_id=owner.id, thread_id=owner_thread.id, run_id=owner_second_run.id, day=date(2026, 9, 2), at=timestamp)
    foreign = _record(user_id=other.id, thread_id=other_thread.id, run_id=other_run.id, day=date(2026, 9, 3), at=timestamp)
    db_session.add_all([first, second, foreign])
    db_session.flush()
    repository = SqlAlchemyDashboardRepository(db_session)

    page_one = repository.get_history_page(user_id=owner.id, cursor=None, limit=1)
    cursor = DashboardHistoryCursor.from_record(page_one[0])
    page_two = repository.get_history_page(user_id=owner.id, cursor=cursor, limit=1)

    assert {page_one[0].id, page_two[0].id} == {first.id, second.id}
    assert page_one[0].id != page_two[0].id
