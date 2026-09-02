"""Real PostgreSQL proof that local-date attribution is explicit and tenant-bound."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.records.models import DashboardTimezoneBackfillAudit, MealRecord
from app.records.repository import SqlAlchemyMealRecordRepository
from app.records.service import MealRecordService


def _user(*, label: str) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(), email=f"timezone-{label}-{uuid.uuid4().hex}@example.test", password_hash="digest",
        role="user", is_active=True, email_verified_at=now, created_at=now, updated_at=now,
    )


def _legacy_record(*, user_id: uuid.UUID, command_key: str) -> MealRecord:
    now = datetime.now(UTC)
    return MealRecord(
        id=uuid.uuid4(), user_id=user_id, source_run_id=uuid.uuid4(), agent_thread_id=uuid.uuid4(), agent_run_id=uuid.uuid4(),
        command_key=command_key, consumed_at=datetime(2026, 8, 30, 16, 30, tzinfo=UTC),
        nutrition_catalog_version="catalog.v1", calculation_version="rules.v1", energy_kcal=Decimal("1"), protein_g=Decimal("1"), fat_g=Decimal("1"), carbohydrate_g=Decimal("1"),
        created_at=now, updated_at=now, deleted_at=None,
    )


def test_confirmed_timezone_backfill_uses_consumed_at_and_never_crosses_tenants(db_session: Session) -> None:
    owner, other = _user(label="owner"), _user(label="other")
    legacy_owner = _legacy_record(user_id=owner.id, command_key="legacy-owner-key-0001")
    legacy_other = _legacy_record(user_id=other.id, command_key="legacy-other-key-0001")
    db_session.add_all([owner, other, legacy_owner, legacy_other])
    db_session.commit()

    service = MealRecordService(repository=SqlAlchemyMealRecordRepository(db_session), commit=db_session.commit, rollback=db_session.rollback)
    result = service.confirm_dashboard_time_zone(user_id=owner.id, time_zone="Asia/Shanghai")
    db_session.expire_all()
    owner_row = db_session.get(MealRecord, legacy_owner.id)
    other_row = db_session.get(MealRecord, legacy_other.id)
    audit = db_session.scalar(select(DashboardTimezoneBackfillAudit).where(DashboardTimezoneBackfillAudit.user_id == owner.id))

    assert result.dashboard_time_zone == "Asia/Shanghai"
    assert owner_row is not None and owner_row.consumed_local_date == date(2026, 8, 31)
    assert owner_row.local_date_source == "confirmed_timezone_backfill"
    assert other_row is not None and other_row.consumed_local_date is None
    assert audit is not None and audit.confirmed_time_zone == "Asia/Shanghai"
