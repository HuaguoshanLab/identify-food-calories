"""Pure main-graph routing and lifespan contracts.

This module intentionally contains no SQLAlchemy, ORM or repository import.  A
runtime built in later plans injects a `NutritionToolAdapter` and a persisted
checkpointer after AgentService has already proved thread ownership.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from collections.abc import Callable

from app.agent.state import (
    AgentNextAction,
    AgentRuntimeStatus,
    MealAgentState,
    StateMealItem,
    StateToolSummary,
)
from app.agent.tools import NutritionToolAdapter
from app.nutrition.schemas import FoodSearchInput, NutritionCalculationInput, NutritionValidationInput
from app.providers.reasoning.dto import ParseMealRequest, ProviderCallError
from app.providers.reasoning.ports import ReasoningModelProvider


GRAPH_VERSION = "meal-agent-graph.v1"


class AgentIntent(StrEnum):
    MEAL_ANALYSIS = "MEAL_ANALYSIS"
    DIET_PLANNING = "DIET_PLANNING"


class GraphRoute(StrEnum):
    MEAL_ANALYSIS = "MEAL_ANALYSIS"
    DIET_PLANNING = "DIET_PLANNING"


class AgentGraph(Protocol):
    """Compiled graph facade used by HTTP/supervisor lifecycles in later plans."""

    async def ainvoke(self, state: MealAgentState) -> MealAgentState: ...


@dataclass(frozen=True, slots=True)
class AgentRuntime:
    """Long-lived runtime dependencies created once by FastAPI lifespan."""

    graph: AgentGraph
    tools: NutritionToolAdapter
    checkpointer: object
    supervisor: object
    session_factory: Callable[[], object]


class AgentRuntimeFactory(Protocol):
    """Lifecycle seam: create once at startup, never per request or graph node."""

    async def create(self) -> AgentRuntime | None: ...

    async def close(self, runtime: AgentRuntime | None) -> None: ...


class NoopAgentRuntimeFactory:
    """Explicit temporary lifecycle owner until the persisted runtime is wired."""

    async def create(self) -> AgentRuntime | None:
        return None

    async def close(self, runtime: AgentRuntime | None) -> None:
        _ = runtime


def _digest(value: object) -> str:
    """Checkpoint state records only deterministic result digests, never provider text."""

    return hashlib.sha256(repr(value).encode("utf-8")).hexdigest()


class MealAnalysisGraph:
    """Bounded meal graph using a provider observation and deterministic nutrition tools.

    The object deliberately knows nothing about SQLAlchemy, AgentService or HTTP.  Its caller
    has already written the run ledger and proved tenant ownership before invoking it.
    """

    def __init__(
        self, *, provider: ReasoningModelProvider, tools: NutritionToolAdapter
    ) -> None:
        self._provider = provider
        self._tools = tools

    async def ainvoke(self, state: MealAgentState) -> MealAgentState:
        if state.next_action is not AgentNextAction.PARSE or len(state.messages) != 1:
            return state.model_copy(
                update={"status": AgentRuntimeStatus.FAILED, "next_action": AgentNextAction.STOP}
            )
        try:
            parsed = await self._provider.parse_meal(
                ParseMealRequest(meal_description=state.messages[0])
            )
        except ProviderCallError:
            return state.model_copy(
                update={"status": AgentRuntimeStatus.FAILED, "next_action": AgentNextAction.STOP}
            )
        if len(parsed.value.items) != 1:
            return state.model_copy(
                update={"status": AgentRuntimeStatus.WAITING_INPUT, "next_action": AgentNextAction.ASK_USER}
            )
        observation = parsed.value.items[0]
        if observation.grams is None:
            return state.model_copy(
                update={"status": AgentRuntimeStatus.WAITING_INPUT, "next_action": AgentNextAction.ASK_USER}
            )
        search = self._tools.search_food_catalog(
            FoodSearchInput(query=observation.catalog_query or observation.food_name)
        )
        if search.selected_food is None:
            return state.model_copy(
                update={"status": AgentRuntimeStatus.WAITING_INPUT, "next_action": AgentNextAction.ASK_USER}
            )
        calculation = self._tools.calculate_nutrition(
            NutritionCalculationInput(
                food_id=search.selected_food.id,
                catalog_version=search.selected_food.catalog_version,
                grams=observation.grams,
            )
        )
        validation = self._tools.validate_nutrition_result(
            NutritionValidationInput(calculation=calculation)
        )
        if calculation.nutrients is None or validation.action.value not in {"PASS", "WARN"}:
            return state.model_copy(
                update={"status": AgentRuntimeStatus.FAILED, "next_action": AgentNextAction.STOP}
            )
        food = search.selected_food
        nutrients = calculation.nutrients
        report: dict[str, object] = {
            "items": [{
                "name": food.canonical_name,
                "grams": str(observation.grams),
                "energy_kcal": str(nutrients.energy_kcal.quantize(Decimal("0.1"))),
                "protein_g": str(nutrients.protein_g.quantize(Decimal("0.1"))),
                "fat_g": str(nutrients.fat_g.quantize(Decimal("0.1"))),
                "carbohydrate_g": str(nutrients.carbohydrate_g.quantize(Decimal("0.1"))),
                "catalog_version": food.catalog_version,
                "source_name": food.source_name,
                "source_url": food.source_url,
                "calculation_rule_version": calculation.calculation_rule_version,
            }],
            "totals": {
                "energy_kcal": str(nutrients.energy_kcal.quantize(Decimal("0.1"))),
                "protein_g": str(nutrients.protein_g.quantize(Decimal("0.1"))),
                "fat_g": str(nutrients.fat_g.quantize(Decimal("0.1"))),
                "carbohydrate_g": str(nutrients.carbohydrate_g.quantize(Decimal("0.1"))),
            },
            "disclaimer": "普通饮食参考，不替代医疗建议。",
        }
        item = StateMealItem(
            item_id=observation.item_id,
            normalized_name=food.canonical_name,
            grams=observation.grams,
            food_id=food.id,
            catalog_version=food.catalog_version,
            input_version="v1",
        )
        tools = (
            StateToolSummary(tool_name="search", tool_version="nutrition-tools-v1", action=search.action.value, result_digest=_digest(search)),
            StateToolSummary(tool_name="calculate", tool_version="nutrition-tools-v1", action=calculation.action.value, result_digest=_digest(calculation)),
            StateToolSummary(tool_name="validate", tool_version="nutrition-tools-v1", action=validation.action.value, result_digest=_digest(validation)),
        )
        return state.model_copy(
            update={
                "messages": (),
                "items": (item,),
                "tool_summaries": tools,
                "report": report,
                "status": AgentRuntimeStatus.COMPLETED,
                "next_action": AgentNextAction.REPORT,
            }
        )


def route_main_graph(intent: AgentIntent) -> GraphRoute:
    """Keep the main graph's two supported subgraph routes explicit and closed."""

    if intent is AgentIntent.MEAL_ANALYSIS:
        return GraphRoute.MEAL_ANALYSIS
    return GraphRoute.DIET_PLANNING


def diet_planning_not_available(state: MealAgentState) -> MealAgentState:
    """Phase 2 must not imply that the Phase 5 planner exists or produced advice."""

    return state.model_copy(
        update={
            "next_action": AgentNextAction.STOP,
            "status": AgentRuntimeStatus.FAILED,
            "report": {
                "code": "CAPABILITY_NOT_AVAILABLE",
                "message": "饮食规划能力尚未交付。",
            },
        }
    )
