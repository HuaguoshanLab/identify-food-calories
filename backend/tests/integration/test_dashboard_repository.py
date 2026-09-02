"""Real PostgreSQL proof for dashboard aggregation and keyset pagination."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from app.dashboard.repository import SqlAlchemyDashboardRepository
from app.dashboard.schemas import DashboardHistoryCursor
from app.records.models import MealRecord


pytestmark = pytest.mark.skipif(
    __import__("os").environ.get("APP_ENV") != "test",
    reason="requires the guarded PostgreSQL test environment",
)


def _record(*, user_id: uuid.UUID, day: date, at: datetime, deleted_at: datetime | None = None) -> MealRecord:
    return MealRecord(
        id=uuid.uuid4(), user_id=user_id, source_run_id=uuid.uuid4(), agent_thread_id=uuid.uuid4(), agent_run_id=uuid.uuid4(),
        command_key=f"dashboard-{uuid.uuid4().hex}", consumed_at=at, consumed_time_zone="UTC", consumed_local_date=day,
        local_date_source="submitted_time_zone", nutrition_catalog_version="catalog.v1", calculation_version="calculation.v1",
        energy_kcal=Decimal("100.25"), protein_g=Decimal("10.5"), fat_g=Decimal("5.25"), carbohydrate_g=Decimal("20.75"),
        created_at=at, updated_at=at, deleted_at=deleted_at,
    )


def test_daily_aggregates_are_tenant_filtered_and_exclude_soft_deleted_rows(db_session) -> None:
    owner, other = uuid.uuid4(), uuid.uuid4()
    now = datetime(2026, 9, 2, 12, tzinfo=UTC)
    db_session.add_all([
        _record(user_id=owner, day=date(2026, 9, 2), at=now),
        _record(user_id=owner, day=date(2026, 9, 2), at=now - timedelta(hours=1), deleted_at=now),
        _record(user_id=other, day=date(2026, 9, 2), at=now),
    ])
    db_session.flush()

    aggregates = SqlAlchemyDashboardRepository(db_session).get_daily_aggregates(
        user_id=owner, start_date=date(2026, 9, 1), end_date=date(2026, 9, 7)
    )

    assert len(aggregates) == 1
    assert aggregates[0].consumed_local_date == date(2026, 9, 2)
    assert aggregates[0].meal_count == 1
    assert aggregates[0].totals.energy_kcal == Decimal("100.250000")


def test_history_keyset_uses_date_timestamp_and_id_without_leaks_or_duplicates(db_session) -> None:
    owner, other = uuid.uuid4(), uuid.uuid4()
    timestamp = datetime(2026, 9, 2, 12, tzinfo=UTC)
    first = _record(user_id=owner, day=date(2026, 9, 2), at=timestamp)
    second = _record(user_id=owner, day=date(2026, 9, 2), at=timestamp)
    foreign = _record(user_id=other, day=date(2026, 9, 3), at=timestamp)
    db_session.add_all([first, second, foreign])
    db_session.flush()
    repository = SqlAlchemyDashboardRepository(db_session)

    page_one = repository.get_history_page(user_id=owner, cursor=None, limit=1)
    cursor = DashboardHistoryCursor.from_record(page_one[0])
    page_two = repository.get_history_page(user_id=owner, cursor=cursor, limit=1)

    assert {page_one[0].id, page_two[0].id} == {first.id, second.id}
    assert page_one[0].id != page_two[0].id
