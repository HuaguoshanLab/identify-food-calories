"""Closed, safe lifecycle mapping for diet-planning SSE events."""

from __future__ import annotations

import pytest

from app.planning.service import safe_planning_stream_stage


@pytest.mark.parametrize(
    ("event_type", "expected"),
    [
        ("reading_context", "perception"),
        ("needs_input", "awaiting_input"),
        ("tool_calculation", "tool_calculation"),
        ("validation", "validation"),
        ("completed_validated", "completed"),
        ("retryable", "retryable"),
        ("terminal", "terminal"),
    ],
)
def test_diet_planning_events_have_the_same_safe_stage_matrix(
    event_type: str, expected: str
) -> None:
    assert safe_planning_stream_stage(event_type) == expected


def test_planning_interrupt_resume_and_failures_never_claim_completion() -> None:
    assert safe_planning_stream_stage("needs_input") == "awaiting_input"
    assert safe_planning_stream_stage("completed") is None
    assert safe_planning_stream_stage("provider_response") is None
