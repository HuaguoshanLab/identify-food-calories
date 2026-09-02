"""Bounded weekly-review graph contracts driven by frozen fixtures."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path

import pytest

from app.dashboard.weekly_review_graph import WeeklyReviewGraph, WeeklyReviewGraphConfig, WeeklyReviewGraphResult
from app.providers.reasoning.fake import FakeReasoningModelProvider
from tests.evals.fixtures.weekly_review.loader import load_catalog


CATALOG_PATH = Path(__file__).parents[1] / "evals/fixtures/weekly_review/weekly_review_cases.v1.json"


def _cases() -> list[Mapping[str, object]]:
    return load_catalog(CATALOG_PATH)


def _graph(case: Mapping[str, object]) -> tuple[WeeklyReviewGraph, FakeReasoningModelProvider]:
    provider = FakeReasoningModelProvider()
    return WeeklyReviewGraph(provider=provider, config=WeeklyReviewGraphConfig.from_fixture(case["config"])), provider


@pytest.mark.asyncio
@pytest.mark.parametrize("case", _cases(), ids=lambda case: str(case["id"]))
async def test_frozen_cases_keep_calls_and_minimal_ledger_stable(case: Mapping[str, object]) -> None:
    graph, provider = _graph(case)
    result = await graph.ainvoke_fixture(case)
    expected = case["expected"]
    assert isinstance(result, WeeklyReviewGraphResult)
    assert result.code == expected["stable_code"]
    assert result.model_calls == expected["provider_calls"]
    assert result.model_calls <= expected["max_model_calls"] <= 2
    assert len(provider.calls) == expected["provider_calls"]
    assert result.ledger == case["ledger"]
    assert result.ledger_metadata == {
        "facts_digest": case["facts"]["facts_digest"], "prompt_version": "weekly-review-prompt.v1",
        "schema_version": "weekly-review-schema.v1", "graph_version": "weekly-review-graph.v1",
        "runtime_config_version": case["config"]["runtime_config_version"],
    }


@pytest.mark.asyncio
async def test_rejects_sensitive_fact_before_provider_work() -> None:
    case = next(case for case in _cases() if case["id"] == "case-13-privacy-contamination")
    graph, provider = _graph(case)
    contaminated = deepcopy(case)
    contaminated["facts"]["email"] = "private@example.invalid"
    result = await graph.ainvoke_fixture(contaminated)
    assert result.code == "WEEKLY_REVIEW_FACTS_INVALID"
    assert result.model_calls == 0
    assert provider.calls == []


@pytest.mark.asyncio
async def test_unknown_outcome_is_never_replayed() -> None:
    case = next(case for case in _cases() if case["id"] == "case-01-sufficient-variety")
    graph, provider = _graph(case)
    provider.queue_weekly_review_error(kind="OUTCOME_UNKNOWN", code="PROVIDER_OUTCOME_UNKNOWN")
    result = await graph.ainvoke_fixture(case)
    assert result.code == "PROVIDER_OUTCOME_UNKNOWN"
    assert result.model_calls == len(provider.calls) == 1
