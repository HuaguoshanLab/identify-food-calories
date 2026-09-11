"""Vision-to-state boundary tests: no raw image/provider body crosses into the graph state."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast

from app.agent.graph import MealAnalysisGraph
from app.agent.state import AgentNextAction, AgentRuntimeStatus, MealAgentState, StateCandidate, StateImageReference
from app.agent.tools import NutritionToolAdapter
from app.agent.tools import NutritionServiceToolAdapter
from app.nutrition.schemas import QualifiedFood, NutritionValues
from app.nutrition.service import NutritionService
from app.providers.reasoning.dto import ProviderFailureKind
from app.providers.reasoning.fake import FakeReasoningModelProvider
from app.providers.vision.dto import VisionMealItemDTO
from app.providers.vision.fake import FakeVisionModelProvider


class _UnusedTools:
    async def search_food_catalog(self, request: object) -> object:  # pragma: no cover - guard
        raise AssertionError(f"missing grams must interrupt before catalog search: {request!r}")

    def calculate_nutrition(self, request: object) -> object:  # pragma: no cover - guard
        raise AssertionError(f"missing grams must interrupt before calculation: {request!r}")

    def validate_nutrition_result(self, request: object) -> object:  # pragma: no cover - guard
        raise AssertionError(f"missing grams must interrupt before validation: {request!r}")


class _FoodRepository:
    def __init__(self, food: QualifiedFood) -> None:
        self._food = food

    def search_qualified_foods(self, *, normalized_query: str, limit: int) -> list[QualifiedFood]:
        return [self._food] if normalized_query == "米饭" else []

    def get_qualified_food(self, *, food_id: uuid.UUID, catalog_version: str) -> QualifiedFood | None:
        return self._food if (food_id, catalog_version) == (self._food.id, self._food.catalog_version) else None


def _nutrition_tools() -> NutritionToolAdapter:
    food = QualifiedFood(
        id=uuid.uuid4(), canonical_name="熟米饭", catalog_version="fdc-test-v1",
        prepared_state="cooked", source_name="test-source", source_url="https://example.test/source",
        license_name="CC0", aliases=("米饭",),
        nutrients_per_100g=NutritionValues(
            energy_kcal=Decimal("130"), protein_g=Decimal("2.7"), fat_g=Decimal("0.3"), carbohydrate_g=Decimal("28"),
        ),
    )
    return NutritionServiceToolAdapter(service=NutritionService(repository=_FoodRepository(food)))


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


def test_outcome_unknown_does_not_retry_the_same_image(caplog: object) -> None:
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
    assert "vision_provider_failed kind=PROVIDER_OUTCOME_UNKNOWN code=PROVIDER_OUTCOME_UNKNOWN" in caplog.text  # type: ignore[attr-defined]


def test_transient_vision_failure_retries_once_and_records_attempt_count() -> None:
    vision = FakeVisionModelProvider()
    vision.queue_error(kind=ProviderFailureKind.TRANSIENT, code="VISION_TEMPORARY")
    vision.queue_result(
        [VisionMealItemDTO(item_id="rice-1", food_name="米饭", estimated_grams=None, confidence="0.6")]
    )
    graph = MealAnalysisGraph(
        provider=FakeReasoningModelProvider(),
        vision_provider=vision,
        tools=cast(NutritionToolAdapter, _UnusedTools()),
    )

    result = asyncio.run(graph.ainvoke(_state()))

    assert result.status is AgentRuntimeStatus.WAITING_INPUT
    assert result.vision_attempts == 2
    assert len(vision.calls) == 2


def test_estimated_weight_reaches_only_deterministic_nutrition_and_is_reported() -> None:
    vision = FakeVisionModelProvider()
    vision.queue_result(
        [VisionMealItemDTO(item_id="rice-1", food_name="米饭", estimated_grams=Decimal("100"), confidence=Decimal("0.9"))]
    )
    graph = MealAnalysisGraph(
        provider=FakeReasoningModelProvider(), vision_provider=vision, tools=_nutrition_tools()
    )

    result = asyncio.run(graph.ainvoke(_state()))

    assert result.status is AgentRuntimeStatus.COMPLETED
    assert result.report is not None
    item = result.report["items"][0]
    assert item["energy_kcal"] == "130.0"
    assert item["is_estimated"] is True
    assert item["estimate_confidence"] == "0.9"


def test_checkpoint_projection_is_backward_compatible_and_excludes_retrieval_evidence() -> None:
    """Old checkpoints have only the historical display fields; retrieval evidence never persists."""

    candidate = StateCandidate.model_validate(
        {
            "item_id": "rice-1",
            "food_id": str(uuid.uuid4()),
            "catalog_version": "foundation-foods-v1",
            "label": "熟米饭（cooked）",
        }
    )

    assert candidate.canonical_label is None
    assert candidate.relation_label is None
    assert candidate.prepared_state is None
    assert candidate.portion_hints == ()
    serialized = candidate.model_dump_json()
    for forbidden in ("score", "rank", "vector", "query", "provider"):
        assert forbidden not in serialized
