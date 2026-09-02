"""Narrow async port used by graph nodes without importing a vendor SDK."""

from __future__ import annotations

from typing import Protocol

from app.providers.reasoning.dto import (
    ApplyCorrectionRequest,
    ApplyCorrectionResult,
    ParseMealRequest,
    ParseMealResult,
    WeeklyReviewRequest,
    WeeklyReviewResult,
)


class ReasoningModelProvider(Protocol):
    async def parse_meal(self, request: ParseMealRequest) -> ParseMealResult: ...

    async def apply_correction(
        self, request: ApplyCorrectionRequest
    ) -> ApplyCorrectionResult: ...

    async def generate_weekly_review(self, request: WeeklyReviewRequest) -> WeeklyReviewResult: ...
