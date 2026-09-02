from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.auth.models import User, UserRole
from app.dashboard.models import WeeklyReviewResult
from app.dashboard.repository import SqlAlchemyDashboardRepository
from app.dashboard.weekly_review_dto import WeeklyReviewCacheKey


pytestmark = pytest.mark.skipif(
    __import__("os").environ.get("APP_ENV") != "test",
    reason="requires the guarded PostgreSQL test environment",
)


def test_cache_key_is_value_object_and_does_not_store_review_payload() -> None:
    key = WeeklyReviewCacheKey(
        user_id=uuid.uuid4(), week_start=date(2026, 8, 31), facts_digest="a" * 64,
        graph_version="weekly-review-graph-v1", prompt_version="weekly-review-prompt-v1",
        schema_version="weekly-review-schema-v1", runtime_config_version="weekly-review-runtime-v1",
    )
    assert "prompt" not in key.model_dump(exclude={"prompt_version"})
    assert "facts" not in key.model_dump(exclude={"facts_digest"})


def test_postgres_enforces_one_safe_result_per_full_versioned_key(db_session) -> None:
    now = datetime(2026, 9, 2, tzinfo=UTC)
    user = User(id=uuid.uuid4(), email=f"weekly-review-{uuid.uuid4().hex}@example.test", password_hash="digest", role=UserRole.USER.value, is_active=True, email_verified_at=now, created_at=now, updated_at=now)
    db_session.add(user)
    db_session.flush()
    key = WeeklyReviewCacheKey(user_id=user.id, week_start=date(2026, 8, 31), facts_digest="a" * 64, graph_version="weekly-review-graph-v1", prompt_version="weekly-review-prompt-v1", schema_version="weekly-review-schema-v1", runtime_config_version="weekly-review-runtime-v1")
    repository = SqlAlchemyDashboardRepository(db_session)
    saved = repository.save_completed_weekly_review(key=key, advice="keep logging meals", result_digest="b" * 64, now=now)
    assert repository.get_completed_weekly_review(key=key).id == saved.id
    db_session.add(WeeklyReviewResult(user_id=user.id, week_start=key.week_start, facts_digest=key.facts_digest, graph_version=key.graph_version, prompt_version=key.prompt_version, schema_version=key.schema_version, runtime_config_version=key.runtime_config_version, status="completed", advice="duplicate", abstention_code=None, result_digest="c" * 64, agent_run_id=None, created_at=now, updated_at=now))
    with pytest.raises(IntegrityError):
        db_session.flush()
