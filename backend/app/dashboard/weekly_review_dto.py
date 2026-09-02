"""Minimal, provider-safe value objects for the weekly review cache boundary."""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.dashboard.schemas import DashboardNutritionTotals


class WeeklyReviewFacts(BaseModel):
    """Deterministic aggregates only; raw meal text and provider payloads never cross this DTO."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    week_start: date
    coverage_days: int = Field(ge=0, le=7)
    meal_count: int = Field(ge=0)
    totals: DashboardNutritionTotals
    approved_patterns: tuple[str, ...] = ()


class WeeklyReviewCacheKey(BaseModel):
    """All cache dimensions are explicit, so safety-version changes naturally miss."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    user_id: uuid.UUID
    week_start: date
    facts_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    graph_version: str = Field(min_length=1, max_length=80)
    prompt_version: str = Field(min_length=1, max_length=80)
    schema_version: str = Field(min_length=1, max_length=80)
    runtime_config_version: str = Field(min_length=1, max_length=80)


class WeeklyReviewResponse(BaseModel):
    """A client-safe review: facts plus validated advice or a closed abstention code."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    facts: WeeklyReviewFacts
    cache_key: WeeklyReviewCacheKey | None = None
    advice: str | None = Field(default=None, max_length=500)
    abstention_code: str | None = Field(default=None, max_length=80)
