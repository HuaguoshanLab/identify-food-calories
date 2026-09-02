"""Frozen weekly-review eval runner; fixtures remain the sole case definition."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from app.dashboard.weekly_review_graph import WeeklyReviewGraph, WeeklyReviewGraphConfig
from app.providers.reasoning.fake import FakeReasoningModelProvider
from tests.evals.fixtures.weekly_review.loader import load_catalog


CATALOG_PATH = Path(__file__).parent / "fixtures/weekly_review/weekly_review_cases.v1.json"


@pytest.mark.asyncio
@pytest.mark.parametrize("case", load_catalog(CATALOG_PATH), ids=lambda case: str(case["id"]))
async def test_frozen_weekly_review_catalog(case: Mapping[str, object]) -> None:
    provider = FakeReasoningModelProvider()
    graph = WeeklyReviewGraph(provider=provider, config=WeeklyReviewGraphConfig.from_fixture(case["config"]))
    result = await graph.ainvoke_fixture(case)
    expected = case["expected"]
    assert result.code == expected["stable_code"]
    assert result.model_calls == expected["provider_calls"]
    assert result.model_calls <= expected["max_model_calls"]
    assert result.ledger["model_calls"] == expected["provider_calls"]
    assert result.ledger["invocation_count"] == expected["provider_calls"]
    assert result.ledger_metadata.keys() == {"facts_digest", "prompt_version", "schema_version", "graph_version", "runtime_config_version"}
