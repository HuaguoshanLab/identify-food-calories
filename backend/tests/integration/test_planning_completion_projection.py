"""RED PostgreSQL evidence for completed-plan projection constraints and revocation."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from app.auth.models import User, UserRole
from app.planning.models import PlanningCompletionProjection, PlanningProfile


def test_completion_projection_rejects_orphans_and_exposes_no_cross_user_target(db_session) -> None:
    if os.environ.get("APP_ENV") != "test":
        return
    now = datetime(2026, 9, 2, tzinfo=UTC)
    user = User(
        id=uuid.uuid4(), email=f"projection-{uuid.uuid4().hex}@example.test", password_hash="digest",
        role=UserRole.USER.value, is_active=True, email_verified_at=now, created_at=now, updated_at=now,
    )
    db_session.add(user)
    db_session.flush()

    projection = PlanningCompletionProjection(
        id=uuid.uuid4(), user_id=user.id, completed_run_id=uuid.uuid4(), completed_thread_id=uuid.uuid4(),
        profile_revision=1, target_version="target-policy.v1", energy_kcal_lower=Decimal("1800"),
        energy_kcal_upper=Decimal("2000"), carbohydrate_g_lower=Decimal("200"), carbohydrate_g_upper=Decimal("300"),
        protein_g_lower=Decimal("80"), protein_g_upper=Decimal("120"), fat_g_lower=Decimal("40"),
        fat_g_upper=Decimal("70"), completed_at=now, revoked_at=None, revocation_reason=None,
    )
    db_session.add(projection)
    with pytest.raises(IntegrityError):
        db_session.flush()
