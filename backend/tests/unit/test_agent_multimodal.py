"""Vision-to-state boundary tests: no raw image/provider body crosses into the graph state."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast

from app.agent.graph import MealAnalysisGraph
from app.agent.state import AgentNextAction, AgentRuntimeStatus, MealAgentState, StateImageReference
from app.agent.tools import NutritionToolAdapter
from app.providers.reasoning.dto import ProviderFailureKind
from app.providers.reasoning.fake import FakeReasoningModelProvider
from app.providers.vision.dto import VisionMealItemDTO
from app.providers.vision.fake import FakeVisionModelProvider


class _UnusedTools:
    def search_food_catalog(self, request: object) -> object:  # pragma: no cover - guard
        raise AssertionError(f"missing grams must interrupt before catalog search: {request!r}")

    def calculate_nutrition(self, request: object) -> object:  # pragma: no cover - guard
        raise AssertionError(f"missing grams must interrupt before calculation: {request!r}")

    def validate_nutrition_result(self, request: object) -> object:  # pragma: no cover - guard
        raise AssertionError(f"missing grams must interrupt before validation: {request!r}")


def _state() -> MealAgentState:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return MealAgentState(
        user_id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        graph_version="meal-agent-graph.v1",
        prompt_version="vision-meal.v1",
        tool_version="nutrition-tools-v1",
        next_action=AgentNextAction.VISION,
        vision_image=StateImageReference(
            image_id=uuid.uuid4(),
            digest_sha256="a" * 64,
            mime_type="image/jpeg",
            width=12,
            height=8,
            byte_size=12,
            locator="b" * 32 + ".jpg",
            created_at=now,
            expires_at=now + timedelta(minutes=5),
            status="ready",
        ),
        vision_invocation_status="prepared",
    )


def test_vision_items_become_safe_estimated_state_and_one_combined_clarification() -> None:
    vision = FakeVisionModelProvider()
    vision.queue_result(
        [
            VisionMealItemDTO(
                item_id="rice-1",
                food_name="米饭",
                estimated_grams=None,
                confidence=Decimal("0.6"),
            )
        ]
    )
    graph = MealAnalysisGraph(
        provider=FakeReasoningModelProvider(),
        vision_provider=vision,
        tools=cast(NutritionToolAdapter, _UnusedTools()),
    )

    result = asyncio.run(graph.ainvoke(_state()))

    assert result.status is AgentRuntimeStatus.WAITING_INPUT
    assert result.vision_invocation_status == "completed"
    assert result.items[0].is_estimated is False
    assert result.items[0].estimate_confidence == Decimal("0.6")
    assert len(result.clarification_questions) == 1
    assert result.clarification_questions[0].field == "grams"
    assert len(vision.calls) == 1
    serialized = result.model_dump_json()
    assert "base64" not in serialized and "normalized-image-bytes" not in serialized


def test_outcome_unknown_does_not_retry_the_same_image() -> None:
    vision = FakeVisionModelProvider()
    vision.queue_error(kind=ProviderFailureKind.OUTCOME_UNKNOWN, code="PROVIDER_OUTCOME_UNKNOWN")
    graph = MealAnalysisGraph(
        provider=FakeReasoningModelProvider(),
        vision_provider=vision,
        tools=cast(NutritionToolAdapter, _UnusedTools()),
    )

    result = asyncio.run(graph.ainvoke(_state()))

    assert result.status is AgentRuntimeStatus.FAILED
    assert result.vision_invocation_status == "outcome_unknown"
    assert len(vision.calls) == 1
