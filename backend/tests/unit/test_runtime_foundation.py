"""Public runtime contract for the application foundation."""

from __future__ import annotations

import ast
import asyncio
import inspect
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings


def test_deepseek_provider_uses_schema_and_never_retries_unknown_transport_outcome() -> None:
    """The paid adapter must stay testable through HTTPX MockTransport only."""

    import httpx

    from app.providers.reasoning.deepseek import DeepSeekReasoningModelProvider
    from app.providers.reasoning.dto import ParseMealRequest, ProviderCallError, ProviderFailureKind

    requests: list[httpx.Request] = []

    def network_failure(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        raise httpx.ReadTimeout("response status is unknown", request=request)

    provider = DeepSeekReasoningModelProvider(
        api_key="test-key",
        model="deepseek-v4-flash",
        timeout_seconds=20,
        price_snapshot={"input_usd_per_m": "1", "output_usd_per_m": "2"},
        transport=httpx.MockTransport(network_failure),
    )

    with pytest.raises(ProviderCallError) as error:
        asyncio.run(provider.parse_meal(ParseMealRequest(meal_description="米饭 100 克")))

    assert error.value.kind is ProviderFailureKind.OUTCOME_UNKNOWN
    assert error.value.code == "PROVIDER_OUTCOME_UNKNOWN"
    assert len(requests) == 1


def test_deepseek_provider_retries_only_safe_transient_response_and_validates_json() -> None:
    import httpx

    from app.providers.reasoning.deepseek import DeepSeekReasoningModelProvider
    from app.providers.reasoning.dto import ParseMealRequest, ProviderCallError, ProviderFailureKind

    attempts = 0

    def transient_then_valid(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, request=request, json={"error": {"message": "hidden"}})
        return httpx.Response(
            200,
            request=request,
            headers={"x-request-id": "safe-request-id"},
            json={
                "status": "completed",
                "output": [{"type": "message", "content": [{"type": "output_text", "text": '{"items":[{"item_id":"rice-1","food_name":"米饭","grams":"100"}]}'}]}],
                "usage": {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
            },
        )

    provider = DeepSeekReasoningModelProvider(
        api_key="test-key",
        model="deepseek-v4-flash",
        timeout_seconds=20,
        price_snapshot={"input_usd_per_m": "1", "output_usd_per_m": "2"},
        transport=httpx.MockTransport(transient_then_valid),
    )
    result = asyncio.run(provider.parse_meal(ParseMealRequest(meal_description="米饭 100 克")))

    assert attempts == 2
    assert result.metadata.provider_request_id == "safe-request-id"
    assert result.metadata.usage.cost_usd == Decimal("0.00014")

    invalid_schema = DeepSeekReasoningModelProvider(
        api_key="test-key",
        model="deepseek-v4-flash",
        timeout_seconds=20,
        price_snapshot={"input_usd_per_m": "1", "output_usd_per_m": "2"},
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                request=request,
                json={
                    "status": "completed",
                    "output": [{"type": "message", "content": [{"type": "output_text", "text": "{}"}]}],
                    "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                },
            )
        ),
    )
    with pytest.raises(ProviderCallError) as schema_error:
        asyncio.run(invalid_schema.parse_meal(ParseMealRequest(meal_description="米饭 100 克")))
    assert schema_error.value.kind is ProviderFailureKind.PERMANENT
    assert schema_error.value.code == "PROVIDER_SCHEMA_INVALID"


def test_production_deepseek_config_fails_closed_without_complete_model_price_snapshot() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="DEEPSEEK_MODEL"):
        Settings(
            app_env="production",
            database_url="postgresql+psycopg://db.example/food_agent",
            secret_key="x" * 32,
            cookie_secure=True,
            cors_origins=["https://app.example"],
            smtp_host="smtp.example",
            smtp_from_email="noreply@example.com",
            smtp_username="mailer",
            smtp_password="password",
            reasoning_provider_mode="deepseek",
            deepseek_api_key="test-key",
            _env_file=None,
        )


class _RecordingNutritionTools:
    """Deterministic test double that records item-scoped tool calls, not model values."""

    def __init__(self) -> None:
        from app.nutrition.schemas import NutritionValues, QualifiedFood

        self.rice = QualifiedFood(
            id=uuid.UUID('11111111-1111-4111-8111-111111111111'), canonical_name='熟米饭',
            catalog_version='fdc-v1', prepared_state='cooked', source_name='FDC',
            source_url='https://fdc.example/rice', license_name='CC0', aliases=('米饭',),
            nutrients_per_100g=NutritionValues(energy_kcal=Decimal('130'), protein_g=Decimal('2.7'), fat_g=Decimal('0.3'), carbohydrate_g=Decimal('28.2')),
        )
        self.egg = QualifiedFood(
            id=uuid.UUID('22222222-2222-4222-8222-222222222222'), canonical_name='鸡蛋',
            catalog_version='fdc-v1', prepared_state='whole', source_name='FDC',
            source_url='https://fdc.example/egg', license_name='CC0', aliases=('鸡蛋',),
            nutrients_per_100g=NutritionValues(energy_kcal=Decimal('143'), protein_g=Decimal('12.6'), fat_g=Decimal('9.5'), carbohydrate_g=Decimal('0.7')),
        )
        self.calls: list[tuple[str, str]] = []

    def search_food_catalog(self, request: object):
        from app.nutrition.schemas import FoodSearchResult, NutritionAction

        query = request.query
        self.calls.append(('search', query))
        if query == 'ambiguous':
            return FoodSearchResult(action=NutritionAction.ASK, query=query, candidates=(self.rice, self.egg), safe_message='choose')
        if query == 'unknown':
            return FoodSearchResult(action=NutritionAction.ASK, query=query, safe_message='unknown')
        food = self.egg if query == '鸡蛋' else self.rice
        return FoodSearchResult(action=NutritionAction.PASS, query=query, selected_food=food, safe_message='matched')

    def calculate_nutrition(self, request: object):
        from app.nutrition.schemas import NutritionAction, NutritionCalculationResult, NutritionValues

        food = self.egg if request.food_id == self.egg.id else self.rice
        self.calls.append(('calculate', str(food.id)))
        factor = request.grams / Decimal('100')
        source = food.nutrients_per_100g
        return NutritionCalculationResult(
            action=NutritionAction.PASS, food=food, grams=request.grams,
            nutrients=NutritionValues(energy_kcal=source.energy_kcal * factor, protein_g=source.protein_g * factor, fat_g=source.fat_g * factor, carbohydrate_g=source.carbohydrate_g * factor),
            safe_message='calculated',
        )

    def validate_nutrition_result(self, request: object):
        from app.nutrition.schemas import NutritionAction, NutritionValidationResult

        self.calls.append(('validate', str(request.calculation.food.id)))
        return NutritionValidationResult(action=NutritionAction.PASS, rule_id='pass', safe_message='valid')


def _initial_state() -> object:
    from app.agent.state import MealAgentState

    return MealAgentState(
        user_id=uuid.uuid4(), thread_id=uuid.uuid4(), run_id=uuid.uuid4(), messages=('test meal',),
        graph_version='graph-v1', prompt_version='prompt-v1', tool_version='tools-v1',
    )


def _graph_with_items(*items: object):
    from app.agent.graph import MealAnalysisGraph
    from app.providers.reasoning.dto import ParsedMealDTO
    from app.providers.reasoning.fake import FakeReasoningModelProvider

    provider = FakeReasoningModelProvider()
    provider.queue_parse_result(ParsedMealDTO(items=list(items)))
    tools = _RecordingNutritionTools()
    return MealAnalysisGraph(provider=provider, tools=tools), provider, tools


def test_graph_aggregates_questions_and_resume_does_not_repeat_parse() -> None:
    from app.providers.reasoning.dto import ParsedMealItemDTO

    graph, provider, tools = _graph_with_items(
        ParsedMealItemDTO(item_id='rice-1', food_name='米饭', catalog_query='米饭'),
        ParsedMealItemDTO(item_id='egg-1', food_name='鸡蛋', catalog_query='鸡蛋'),
    )
    waiting = asyncio.run(graph.ainvoke(_initial_state()))

    assert waiting.status.value == 'waiting_input'
    assert {question.item_id for question in waiting.clarification_questions} == {'rice-1', 'egg-1'}
    assert len(provider.calls) == 1
    assert tools.calls == []

    completed = asyncio.run(graph.ainvoke(waiting, resume={'answers': {'rice-1': {'grams': '100'}, 'egg-1': {'grams': '55'}}}))

    assert completed.status.value == 'completed'
    assert len(provider.calls) == 1
    assert completed.report is not None and completed.report['is_partial'] is False
    assert len(tools.calls) == 6


def test_graph_never_auto_selects_ambiguous_candidate_and_keeps_invalid_resume_waiting() -> None:
    from app.providers.reasoning.dto import ParsedMealItemDTO

    graph, provider, tools = _graph_with_items(
        ParsedMealItemDTO(item_id='food-1', food_name='米饭', catalog_query='ambiguous', grams=Decimal('100')),
    )
    waiting = asyncio.run(graph.ainvoke(_initial_state()))

    assert waiting.status.value == 'waiting_input'
    question = waiting.clarification_questions[0]
    assert question.field == 'food' and len(question.candidates) == 2
    assert waiting.items[0].food_id is None
    invalid = asyncio.run(graph.ainvoke(waiting, resume={'answers': {'food-1': {'candidate_id': str(uuid.uuid4())}}}))
    assert invalid == waiting and len(provider.calls) == 1 and len(tools.calls) == 1

    completed = asyncio.run(graph.ainvoke(waiting, resume={'answers': {'food-1': {'candidate_id': str(question.candidates[0].food_id)}}}))
    assert completed.status.value == 'completed' and len(provider.calls) == 1


def test_graph_partial_and_correction_recalculate_only_dirty_item() -> None:
    from app.providers.reasoning.dto import ParsedMealItemDTO

    graph, _provider, tools = _graph_with_items(
        ParsedMealItemDTO(item_id='rice-1', food_name='米饭', catalog_query='米饭', grams=Decimal('100')),
        ParsedMealItemDTO(item_id='unknown-1', food_name='未知菜', catalog_query='unknown', grams=Decimal('50')),
    )
    partial = asyncio.run(graph.ainvoke(_initial_state()))
    assert partial.status.value == 'completed'
    assert partial.report is not None and partial.report['is_partial'] is True
    assert partial.unaccounted_items == ('unknown-1',)
    calls_before = list(tools.calls)

    corrected = asyncio.run(graph.ainvoke(partial, resume={'corrections': {'rice-1': {'grams': '150'}}}))
    assert corrected.status.value == 'completed'
    assert corrected.items[1].nutrients is None
    assert tools.calls[len(calls_before):] == [
        ('calculate', '11111111-1111-4111-8111-111111111111'),
        ('validate', '11111111-1111-4111-8111-111111111111'),
    ]


def test_health_endpoint_has_versioned_stable_contract() -> None:
    from app.main import create_app

    settings = Settings(
        app_env="test",
        database_url="postgresql+psycopg://postgres:postgres@localhost:5432/food_agent_dev",
        test_database_url=(
            "postgresql+psycopg://postgres:postgres@localhost:55432/food_agent_test"
        ),
        _env_file=None,
    )
    client = TestClient(create_app(settings))

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "v1"}


class _FakeAgentRepository:
    """Small recording fake: unit tests prove service policy without PostgreSQL."""

    def __init__(self, *, thread: object) -> None:
        self.thread = thread
        self.run = None
        self.owner_queries: list[tuple[uuid.UUID, uuid.UUID]] = []

    def add_thread(self, thread: object) -> object:
        self.thread = thread
        return thread

    def get_thread_for_user(
        self, *, thread_id: uuid.UUID, user_id: uuid.UUID, for_update: bool = False
    ) -> object | None:
        self.owner_queries.append((thread_id, user_id))
        if self.thread.id == thread_id and self.thread.user_id == user_id:
            return self.thread
        return None

    def add_run(self, run: object) -> object:
        self.run = run
        return run

    def get_run_for_command_for_user(
        self,
        *,
        thread_id: uuid.UUID,
        user_id: uuid.UUID,
        command_key: str,
        for_update: bool = False,
    ) -> object | None:
        if (
            self.run is not None
            and self.run.thread_id == thread_id
            and self.run.user_id == user_id
            and self.run.command_key == command_key
        ):
            return self.run
        return None


def test_runtime_contract_keeps_state_separate_and_command_keys_tenant_scoped() -> None:
    from app.agent.models import AgentThread
    from app.agent.service import AgentCommandConflict, AgentService
    from app.agent.state import MealAgentState

    user_id = uuid.uuid4()
    thread_id = uuid.uuid4()
    now = datetime(2026, 8, 29, tzinfo=UTC)
    thread = AgentThread(
        id=thread_id,
        user_id=user_id,
        status="open",
        revision=0,
        created_at=now,
        last_activity_at=now,
        deleted_at=None,
    )
    repository = _FakeAgentRepository(thread=thread)
    service = AgentService(repository=repository, now=lambda: now)

    run = service.create_or_reuse_run(
        thread_id=thread_id,
        user_id=user_id,
        command_key="client-command-1",
        canonical_command={"kind": "description", "text": "米饭 100 克"},
    )
    reused = service.create_or_reuse_run(
        thread_id=thread_id,
        user_id=user_id,
        command_key="client-command-1",
        canonical_command={"text": "米饭 100 克", "kind": "description"},
    )

    assert reused is run
    assert repository.owner_queries == [(thread_id, user_id), (thread_id, user_id)]
    assert len(run.command_hash) == 64
    with pytest.raises(AgentCommandConflict):
        service.create_or_reuse_run(
            thread_id=thread_id,
            user_id=user_id,
            command_key="client-command-1",
            canonical_command={"kind": "description", "text": "面条 100 克"},
        )

    state = MealAgentState(
        user_id=user_id,
        thread_id=thread_id,
        run_id=run.id,
        graph_version=run.graph_version,
        prompt_version=run.prompt_version,
        tool_version=run.tool_version,
    )
    assert state.model_dump(mode="json")["image_refs"] == []
    assert "sqlalchemy" not in inspect.getsource(__import__("app.agent.state", fromlist=["*"])).lower()


def test_agent_import_boundaries_require_graph_to_use_only_tool_adapter() -> None:
    from app.agent import graph, tools

    graph_source = inspect.getsource(graph)
    tools_source = inspect.getsource(tools)
    imported_modules = {
        alias.name
        for node in ast.walk(ast.parse(graph_source))
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    imported_modules.update(
        node.module
        for node in ast.walk(ast.parse(graph_source))
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )

    assert "NutritionToolAdapter" in graph_source
    assert not any(module.startswith("sqlalchemy") for module in imported_modules)
    assert "app.agent.models" not in imported_modules
    assert "app.agent.repository" not in imported_modules
    assert "NutritionService" in tools_source
