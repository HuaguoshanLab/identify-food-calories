from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import uuid

from app.dashboard.repository import DashboardDailyAggregate
from app.dashboard.schemas import DashboardNutritionTotals
from app.dashboard.service import WeeklyReviewService


class DailyRepository:
    def get_daily_aggregates(self, *, user_id, start_date, end_date):
        return [DashboardDailyAggregate(
            consumed_local_date=start_date, meal_count=8,
            totals=DashboardNutritionTotals(energy_kcal=Decimal("1600"), protein_g=Decimal("80"), fat_g=Decimal("50"), carbohydrate_g=Decimal("180")),
        )]


class MemoryCache:
    def __init__(self) -> None:
        self.values = {}

    def get_completed(self, *, key):
        return self.values.get(key)

    def save_completed(self, *, key, advice, agent_run_id=None):
        self.values[key] = advice
        return advice


def test_cache_hit_has_zero_provider_calls_and_versions_change_key() -> None:
    calls = 0

    def provider(_facts):
        nonlocal calls
        calls += 1
        return "eat consistently"

    cache = MemoryCache()
    base_kwargs = dict(repository=DailyRepository(), cache_repository=cache, provider=provider, now=lambda: datetime(2026, 9, 3, 9, tzinfo=UTC))
    user_id = uuid.uuid4()
    first = WeeklyReviewService(**base_kwargs).get_weekly_review(user_id=user_id)
    second = WeeklyReviewService(**base_kwargs).get_weekly_review(user_id=user_id)
    changed = WeeklyReviewService(**base_kwargs, prompt_version="weekly-review-prompt-v2").get_weekly_review(user_id=user_id)

    assert first.advice == second.advice == "eat consistently"
    assert calls == 2
    assert first.cache_key != changed.cache_key
    assert {"user_id", "week_start", "facts_digest", "graph_version", "prompt_version", "schema_version", "runtime_config_version"} == set(first.cache_key.model_dump())
