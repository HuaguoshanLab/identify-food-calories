"""Application-facing wrapper for the pure, facts-only weekly-review graph."""

from __future__ import annotations

from collections.abc import Mapping

from app.dashboard.weekly_review_graph import WeeklyReviewGraph, WeeklyReviewGraphResult


async def run_weekly_review(
    *, graph: WeeklyReviewGraph, facts: Mapping[str, object], facts_digest: str
) -> WeeklyReviewGraphResult:
    """Keep persistence outside the graph; callers may persist only returned safe metadata."""
    return await graph.ainvoke(facts=facts, facts_digest=facts_digest)
