"""Structural guards against collapsing orchestration back into one opaque node."""

from __future__ import annotations

from typing import cast

from app.agent.graph import DietPlanningGraph, MealAnalysisGraph
from app.agent.tools import NutritionToolAdapter, PlanningToolAdapter
from app.providers.reasoning.fake import FakeReasoningModelProvider


def test_meal_graph_has_real_phase_nodes() -> None:
    graph = MealAnalysisGraph(
        provider=FakeReasoningModelProvider(),
        tools=cast(NutritionToolAdapter, object()),
    )

    nodes = set(graph._compiled.get_graph().nodes)  # noqa: SLF001 - architecture guard

    assert {
        "prepare_input",
        "personal_context",
        "vision_recognition",
        "text_parsing",
        "catalog_and_nutrition",
        "deterministic_validation",
        "clarification",
        "report",
    } <= nodes


def test_planning_graph_has_real_phase_nodes() -> None:
    graph = DietPlanningGraph(tools=cast(PlanningToolAdapter, object()))

    nodes = set(graph._compiled.get_graph().nodes)  # noqa: SLF001 - architecture guard

    assert {
        "read_profile",
        "calculate_targets",
        "save_profile",
        "compose_plan",
        "validate_plan",
        "clarification",
        "adjust_plan",
        "complete",
    } <= nodes
