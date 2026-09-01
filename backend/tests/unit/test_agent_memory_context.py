"""Context retrieval is safe guidance and must not change deterministic nutrition totals."""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

from app.agent.graph import MealAnalysisGraph
from app.agent.state import AgentNextAction, AgentRuntimeStatus, MealAgentState
from app.agent.tools import CapturedPreferenceSummary, NutritionServiceToolAdapter
from app.nutrition.schemas import NutritionValues, QualifiedFood
from app.nutrition.service import NutritionService
from app.providers.reasoning.fake import RiceOnlyFakeReasoningModelProvider
from app.retrieval.ports import RetrievedContextItem


class FakeNutritionRepository:
    def __init__(self, food: QualifiedFood) -> None:
        self.food = food

    def search_qualified_foods(self, *, normalized_query: str, limit: int) -> list[QualifiedFood]:
        return [self.food]

    def get_qualified_food(self, *, food_id: uuid.UUID, catalog_version: str) -> QualifiedFood | None:
        return self.food if food_id == self.food.id and catalog_version == self.food.catalog_version else None


class FakeContextService:
    def retrieve(self, *, user_id: uuid.UUID, query: str, catalog_version: str | None = None) -> list[RetrievedContextItem]:
        assert query in {"米饭 100 克", "米饭", "米饭 100 克，我不吃辣"}
        return [RetrievedContextItem(source="preference", summary="已参考你的忌口：不吃花生")]


class FakeExplicitPreferenceCaptureService:
    def __init__(self) -> None:
        self.calls: list[tuple[uuid.UUID, uuid.UUID, str]] = []

    def capture_explicit_preferences(
        self, *, user_id: uuid.UUID, run_id: uuid.UUID, statement: str
    ) -> tuple[CapturedPreferenceSummary, ...]:
        self.calls.append((user_id, run_id, statement))
        if statement == "米饭 100 克，我不吃辣":
            return (CapturedPreferenceSummary(category="avoidance", canonical_text="不吃辣"),)
        return ()


def test_context_is_safe_report_metadata_and_does_not_change_nutrition_calculation() -> None:
    food = QualifiedFood(id=uuid.uuid4(), canonical_name="米饭", catalog_version="fdc-v1", prepared_state="熟", source_name="FDC", source_url="https://fdc.example", license_name="CC0", aliases=("米饭",), nutrients_per_100g=NutritionValues(energy_kcal=Decimal("130"), protein_g=Decimal("2.7"), fat_g=Decimal("0.3"), carbohydrate_g=Decimal("28")))
    tools = NutritionServiceToolAdapter(service=NutritionService(repository=FakeNutritionRepository(food)), context_service=FakeContextService())
    graph = MealAnalysisGraph(provider=RiceOnlyFakeReasoningModelProvider(), tools=tools)
    state = MealAgentState(user_id=uuid.uuid4(), thread_id=uuid.uuid4(), run_id=uuid.uuid4(), messages=("米饭 100 克",), graph_version="v1", prompt_version="v1", tool_version="v1", next_action=AgentNextAction.PARSE, status=AgentRuntimeStatus.ACCEPTED)
    result = asyncio.run(graph.ainvoke(state))
    assert result.report is not None
    assert result.report["totals"]["energy_kcal"] == "130.0"
    assert result.report["context_references"] == ["已参考你的忌口：不吃花生"]
    assert "food_id" not in result.report["context_references"][0]


def test_fresh_text_captures_explicit_preference_once_without_exposing_memory_internals() -> None:
    food = QualifiedFood(id=uuid.uuid4(), canonical_name="米饭", catalog_version="fdc-v1", prepared_state="熟", source_name="FDC", source_url="https://fdc.example", license_name="CC0", aliases=("米饭",), nutrients_per_100g=NutritionValues(energy_kcal=Decimal("130"), protein_g=Decimal("2.7"), fat_g=Decimal("0.3"), carbohydrate_g=Decimal("28")))
    capture = FakeExplicitPreferenceCaptureService()
    tools = NutritionServiceToolAdapter(service=NutritionService(repository=FakeNutritionRepository(food)), context_service=FakeContextService(), explicit_preference_capture_service=capture)
    graph = MealAnalysisGraph(provider=RiceOnlyFakeReasoningModelProvider(), tools=tools)
    state = MealAgentState(user_id=uuid.uuid4(), thread_id=uuid.uuid4(), run_id=uuid.uuid4(), messages=("米饭 100 克，我不吃辣",), graph_version="v1", prompt_version="v1", tool_version="v1", next_action=AgentNextAction.PARSE, status=AgentRuntimeStatus.ACCEPTED)

    result = asyncio.run(graph.ainvoke(state))

    assert len(capture.calls) == 1
    assert result.report is not None
    assert result.report["totals"]["energy_kcal"] == "130.0"
    assert result.explicit_preference_capture_completed is True
    serialized = result.model_dump_json()
    assert "米饭 100 克，我不吃辣" not in serialized
    assert "不吃辣" not in serialized
    assert "direct-memory.v1" not in serialized
    assert "external_memory_id" not in serialized

    replay = asyncio.run(graph.ainvoke(result))
    assert replay.explicit_preference_capture_completed is True
    assert len(capture.calls) == 1


def test_only_fresh_text_can_attempt_direct_preference_capture() -> None:
    food = QualifiedFood(id=uuid.uuid4(), canonical_name="米饭", catalog_version="fdc-v1", prepared_state="熟", source_name="FDC", source_url="https://fdc.example", license_name="CC0", aliases=("米饭",), nutrients_per_100g=NutritionValues(energy_kcal=Decimal("130"), protein_g=Decimal("2.7"), fat_g=Decimal("0.3"), carbohydrate_g=Decimal("28")))
    capture = FakeExplicitPreferenceCaptureService()
    tools = NutritionServiceToolAdapter(service=NutritionService(repository=FakeNutritionRepository(food)), context_service=FakeContextService(), explicit_preference_capture_service=capture)
    graph = MealAnalysisGraph(provider=RiceOnlyFakeReasoningModelProvider(), tools=tools)
    fresh = MealAgentState(user_id=uuid.uuid4(), thread_id=uuid.uuid4(), run_id=uuid.uuid4(), messages=("米饭 100 克",), graph_version="v1", prompt_version="v1", tool_version="v1", next_action=AgentNextAction.PARSE, status=AgentRuntimeStatus.ACCEPTED)

    result = asyncio.run(graph.ainvoke(fresh))

    assert len(capture.calls) == 1
    assert result.explicit_preference_capture_completed is True
    waiting = result.model_copy(update={"next_action": AgentNextAction.ASK_USER, "status": AgentRuntimeStatus.WAITING_INPUT})
    resumed = asyncio.run(graph.ainvoke(waiting, resume={"answers": {}}))
    assert resumed is waiting
    assert len(capture.calls) == 1
