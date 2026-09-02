from __future__ import annotations

import uuid
from datetime import date

from app.dashboard.weekly_review_dto import WeeklyReviewCacheKey


def test_cache_key_is_value_object_and_does_not_store_review_payload() -> None:
    key = WeeklyReviewCacheKey(
        user_id=uuid.uuid4(), week_start=date(2026, 8, 31), facts_digest="a" * 64,
        graph_version="weekly-review-graph-v1", prompt_version="weekly-review-prompt-v1",
        schema_version="weekly-review-schema-v1", runtime_config_version="weekly-review-runtime-v1",
    )
    assert "prompt" not in key.model_dump(exclude={"prompt_version"})
    assert "facts" not in key.model_dump(exclude={"facts_digest"})
