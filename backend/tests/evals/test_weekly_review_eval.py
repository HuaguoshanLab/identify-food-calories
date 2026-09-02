"""Frozen weekly-review eval runner; fixtures remain the sole case definition."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest

from app.dashboard.weekly_review_graph import WeeklyReviewGraph, WeeklyReviewGraphConfig
from app.providers.reasoning.fake import FakeReasoningModelProvider


CATALOG_PATH = Path(__file__).parent / "fixtures/weekly_review/weekly_review_cases.v1.json"


def _cases() -> list[Mapping[str, object]]:
    spec = importlib.util.spec_from_file_location("weekly_review_loader", CATALOG_PATH.parent / "loader.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return [
        {"id": case.id, "facts": case.facts, "config": case.config,
         "provider_script": case.provider_script, "expected": case.expected, "ledger": case.ledger}
        for case in module.load_catalog(CATALOG_PATH)
    ]


@pytest.mark.parametrize("case", _cases(), ids=lambda case: str(case["id"]))
def test_frozen_weekly_review_catalog(case: Mapping[str, object]) -> None:
    provider = FakeReasoningModelProvider()
    graph = WeeklyReviewGraph(provider=provider, config=WeeklyReviewGraphConfig.from_fixture(case["config"]))
    result = asyncio.run(graph.ainvoke_fixture(case))
    expected = case["expected"]
    assert result.code == expected["stable_code"]
    assert result.model_calls == expected["provider_calls"]
    assert result.model_calls <= expected["max_model_calls"]
    assert result.ledger["model_calls"] == expected["provider_calls"]
    assert result.ledger["invocation_count"] == expected["provider_calls"]
    assert result.ledger_metadata.keys() == {"facts_digest", "prompt_version", "schema_version", "graph_version", "runtime_config_version"}
