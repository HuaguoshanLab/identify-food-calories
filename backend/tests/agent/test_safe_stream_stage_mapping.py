"""Closed, safe lifecycle mapping for meal-analysis SSE events."""

from __future__ import annotations

import pytest

from app.agent.service import safe_meal_stream_stage


@pytest.mark.parametrize(
    ("event_type", "expected"),
    [
        ("running", "perception"),
        ("waiting_input", "awaiting_input"),
        ("tool_calculation", "tool_calculation"),
        ("validation", "validation"),
        ("completed_validated", "completed"),
        ("retryable", "retryable"),
        ("terminal", "terminal"),
    ],
)
def test_meal_analysis_events_have_a_complete_safe_stage_matrix(
    event_type: str, expected: str
) -> None:
    assert safe_meal_stream_stage(event_type) == expected


def test_meal_analysis_rejects_unvalidated_completion_and_unknown_nodes() -> None:
    assert safe_meal_stream_stage("completed") is None
    assert safe_meal_stream_stage("parse_provider_payload") is None
