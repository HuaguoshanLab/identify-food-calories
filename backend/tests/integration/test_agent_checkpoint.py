"""Durable-run boundary tests for budgets and provider retry classification.

The PostgreSQL wrapper is deliberately used by the plan verification command.  These focused
tests keep the budget policy deterministic with a fake clock/provider; the vertical suite proves
the same runtime is backed by the real saver and ledger.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import uuid
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
from sqlalchemy.engine import make_url

from app.agent.graph import MealAnalysisGraph
from app.agent.state import AgentBudget, AgentRuntimeStatus, MealAgentState
from app.agent.tools import NutritionToolAdapter
from app.providers.reasoning.dto import (
    ParsedMealDTO,
    ParsedMealItemDTO,
    ProviderFailureKind,
)
from app.providers.reasoning.fake import FakeReasoningModelProvider


BACKEND_ROOT = Path(__file__).resolve().parents[2]


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
    graph = MealAnalysisGraph(provider=provider, tools=cast(NutritionToolAdapter, _UnusedTools()))

    finished = asyncio.run(graph.ainvoke(_state(budget=AgentBudget(model_calls=4))))

    assert finished.status is AgentRuntimeStatus.LIMIT_REACHED
    assert finished.next_action.value == "stop"
    assert provider.calls == []


def test_only_one_transient_provider_retry_is_allowed() -> None:
    provider = FakeReasoningModelProvider()
    provider.queue_parse_error(kind=ProviderFailureKind.TRANSIENT, code="RATE_LIMITED")
    provider.queue_parse_error(kind=ProviderFailureKind.TRANSIENT, code="RATE_LIMITED")
    graph = MealAnalysisGraph(provider=provider, tools=cast(NutritionToolAdapter, _UnusedTools()))

    finished = asyncio.run(graph.ainvoke(_state()))

    assert finished.status is AgentRuntimeStatus.FAILED
    assert len(provider.calls) == 2


def test_real_postgres_saver_reopens_the_same_thread_checkpoint() -> None:
    """A process restart reads the newest persisted state, never an in-memory substitute."""

    from app.core.config import Settings, validate_test_database_configuration
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    if os.environ.get("APP_ENV") != "test":
        pytest.skip("real PostgreSQL proof must use tests/run_pg.py with its explicit test env")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    test_url = validate_test_database_configuration(settings)
    subprocess.run(
        [sys.executable, "scripts/run_initialized_app.py", "--prepare-only"],
        cwd=BACKEND_ROOT,
        env=os.environ.copy(),
        check=True,
    )
    conninfo = make_url(test_url).set(drivername="postgresql").render_as_string(hide_password=False)
    state = _state(budget=AgentBudget(model_calls=4))

    async def persist_then_reopen() -> MealAgentState | None:
        serde = JsonPlusSerializer(pickle_fallback=False, allowed_msgpack_modules=None)
        async with AsyncPostgresSaver.from_conn_string(conninfo, serde=serde) as first:
            graph = MealAnalysisGraph(
                provider=FakeReasoningModelProvider(),
                tools=cast(NutritionToolAdapter, _UnusedTools()),
                checkpointer=first,
            )
            await graph.ainvoke(state)
        async with AsyncPostgresSaver.from_conn_string(conninfo, serde=serde) as second:
            reopened_graph = MealAnalysisGraph(
                provider=FakeReasoningModelProvider(),
                tools=cast(NutritionToolAdapter, _UnusedTools()),
                checkpointer=second,
            )
            return await reopened_graph.aget_state(state.thread_id)

    reopened = asyncio.run(persist_then_reopen())
    assert reopened is not None
    assert reopened.thread_id == state.thread_id
    assert reopened.run_id == state.run_id
