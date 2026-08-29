"""Durable-run boundary tests for budgets and provider retry classification.

The PostgreSQL wrapper is deliberately used by the plan verification command.  These focused
tests keep the budget policy deterministic with a fake clock/provider; the vertical suite proves
the same runtime is backed by the real saver and ledger.
"""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

from app.agent.graph import MealAnalysisGraph
from app.agent.state import AgentBudget, AgentRuntimeStatus, MealAgentState
from app.providers.reasoning.dto import (
    ParsedMealDTO,
    ParsedMealItemDTO,
    ProviderFailureKind,
)
from app.providers.reasoning.fake import FakeReasoningModelProvider


class _UnusedTools:
    def search_food_catalog(self, request: object) -> object:  # pragma: no cover - boundary guard
        raise AssertionError(f"budget should stop before tools: {request!r}")

    def calculate_nutrition(self, request: object) -> object:  # pragma: no cover - boundary guard
        raise AssertionError(f"budget should stop before tools: {request!r}")

    def validate_nutrition_result(self, request: object) -> object:  # pragma: no cover - boundary guard
        raise AssertionError(f"budget should stop before tools: {request!r}")


def _state(*, budget: AgentBudget | None = None) -> MealAgentState:
    return MealAgentState(
        user_id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        messages=("米饭 100 克",),
        graph_version="graph-v1",
        prompt_version="prompt-v1",
        tool_version="tools-v1",
        budget=budget or AgentBudget(),
    )


def test_graph_stops_before_the_next_provider_call_at_model_budget() -> None:
    provider = FakeReasoningModelProvider()
    provider.queue_parse_result(
        ParsedMealDTO(items=[ParsedMealItemDTO(item_id="rice-1", food_name="米饭", grams=Decimal("100"))])
    )
    graph = MealAnalysisGraph(provider=provider, tools=_UnusedTools())

    finished = asyncio.run(graph.ainvoke(_state(budget=AgentBudget(model_calls=4))))

    assert finished.status is AgentRuntimeStatus.LIMIT_REACHED
    assert finished.next_action.value == "stop"
    assert provider.calls == []


def test_only_one_transient_provider_retry_is_allowed() -> None:
    provider = FakeReasoningModelProvider()
    provider.queue_parse_error(kind=ProviderFailureKind.TRANSIENT, code="RATE_LIMITED")
    provider.queue_parse_error(kind=ProviderFailureKind.TRANSIENT, code="RATE_LIMITED")
    graph = MealAnalysisGraph(provider=provider, tools=_UnusedTools())

    finished = asyncio.run(graph.ainvoke(_state()))

    assert finished.status is AgentRuntimeStatus.FAILED
    assert len(provider.calls) == 2
