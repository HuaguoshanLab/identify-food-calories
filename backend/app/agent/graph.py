"""Pure main-graph routing and lifespan contracts.

This module intentionally contains no SQLAlchemy, ORM or repository import.  A
runtime built in later plans injects a `NutritionToolAdapter` and a persisted
checkpointer after AgentService has already proved thread ownership.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from app.agent.state import AgentNextAction, AgentRuntimeStatus, MealAgentState
from app.agent.tools import NutritionToolAdapter


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
