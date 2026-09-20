"""Public runtime contract for the application foundation."""

from __future__ import annotations

import ast
import asyncio
import inspect
import json
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


def test_deepseek_parse_rejects_internal_item_id_as_food_name_and_sends_contract() -> None:
    """A provider placeholder must never reach catalog search as a user food name."""

    import httpx

    from app.providers.reasoning.deepseek import DeepSeekReasoningModelProvider
    from app.providers.reasoning.dto import ParseMealRequest, ProviderCallError

    captured_instructions: list[str] = []

    def placeholder_response(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        captured_instructions.append(body["instructions"])
        return httpx.Response(
            200,
            request=request,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": (
                                    '{"items":[{"item_id":"item_1","food_name":"item_1",'
                                    '"catalog_query":"item_1","grams":"100"}]}'
                                ),
                            }
                        ],
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            },
        )

    provider = DeepSeekReasoningModelProvider(
        api_key="test-key",
        model="deepseek-v4-flash",
        timeout_seconds=20,
        price_snapshot={"input_usd_per_m": "1", "output_usd_per_m": "2"},
        transport=httpx.MockTransport(placeholder_response),
    )

    with pytest.raises(ProviderCallError) as error:
        asyncio.run(provider.parse_meal(ParseMealRequest(meal_description="米饭 100g")))

    assert error.value.code == "PROVIDER_SCHEMA_INVALID"
    assert captured_instructions and "food_name must be the actual food name" in captured_instructions[0]
    assert "item_id is an internal" in captured_instructions[0]


def test_parsed_meal_item_uses_food_name_when_optional_query_is_internal_id() -> None:
    """A valid model observation keeps retrieval on the validated food name."""

    from app.providers.reasoning.dto import ParsedMealItemDTO

    item = ParsedMealItemDTO(
        item_id="item_1", food_name="米饭", catalog_query="item_1", grams=Decimal("100")
    )

    assert item.catalog_query is None


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


def test_tracing_config_and_allowlist_redact_sensitive_attributes() -> None:
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    from pydantic import ValidationError

    from app.core.tracing import create_tracing_runtime

    with pytest.raises(ValidationError, match="TRACING_COLLECTOR_ENDPOINT"):
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
            deepseek_model="deepseek-v4-flash",
            deepseek_price_snapshot_version="price-v1",
            deepseek_input_usd_per_m="1",
            deepseek_output_usd_per_m="2",
            tracing_enabled=True,
            _env_file=None,
        )

    exporter = InMemorySpanExporter()
    settings = Settings(
        tracing_enabled=True,
        tracing_collector_endpoint="https://collector.example/v1/traces",
        tracing_hmac_key="trace-hmac-key",
        tracing_service_name="food-agent",
        tracing_service_version="v1",
        _env_file=None,
    )
    runtime = create_tracing_runtime(settings, exporter=exporter)
    with runtime.span(
        "agent.run",
        {
            "node.name": "parse",
            "token.input": 12,
            "meal.text": "米饭 100 克",
            "user.id": "user-123",
            "prompt": "ignore safeguards",
            "chain_of_thought": "hidden",
        },
    ):
        pass
    runtime.flush()

    attributes = dict(exporter.get_finished_spans()[0].attributes or {})
    assert attributes["node.name"] == "parse"
    assert attributes["token.input"] == 12
    assert all("米饭" not in str(value) for value in attributes.values())
    assert not {"meal.text", "user.id", "prompt", "chain_of_thought"} & set(attributes)


class _RecordingNutritionTools:
    """Deterministic test double that records item-scoped tool calls, not model values."""

    def __init__(self) -> None:
        from app.nutrition.schemas import ControlledPortion, NutritionValues, QualifiedFood

        self.rice = QualifiedFood(
            id=uuid.UUID('11111111-1111-4111-8111-111111111111'), canonical_name='熟米饭',
            catalog_version='fdc-v1', prepared_state='cooked', source_name='FDC',
            source_url='https://fdc.example/rice', license_name='CC0', aliases=('米饭',),
            portions=(ControlledPortion(description='一拳', grams=Decimal('120'), source_reference='expert-review', version='rice-fist-v1'),),
            nutrients_per_100g=NutritionValues(energy_kcal=Decimal('130'), protein_g=Decimal('2.7'), fat_g=Decimal('0.3'), carbohydrate_g=Decimal('28.2')),
        )
        self.egg = QualifiedFood(
            id=uuid.UUID('22222222-2222-4222-8222-222222222222'), canonical_name='鸡蛋',
            catalog_version='fdc-v1', prepared_state='whole', source_name='FDC',
            source_url='https://fdc.example/egg', license_name='CC0', aliases=('鸡蛋',),
            nutrients_per_100g=NutritionValues(energy_kcal=Decimal('143'), protein_g=Decimal('12.6'), fat_g=Decimal('9.5'), carbohydrate_g=Decimal('0.7')),
        )
        self.calls: list[tuple[str, str]] = []

    async def search_food_catalog(self, request: object):
        from app.nutrition.schemas import FoodRelation, FoodSearchCandidate, FoodSearchResult, NutritionAction

        query = request.query
        self.calls.append(('search', query))
        if query == 'ambiguous':
            return FoodSearchResult(
                action=NutritionAction.ASK,
                query=query,
                candidates=tuple(
                    FoodSearchCandidate(
                        food_id=food.id,
                        catalog_version=food.catalog_version,
                        canonical_name=food.canonical_name,
                        relation=FoodRelation.SAME_CLASS,
                        prepared_state=food.prepared_state,
                        source_name=food.source_name,
                    )
                    for food in (self.rice, self.egg)
                ),
                safe_message='choose',
            )
        if query == 'unknown':
            return FoodSearchResult(action=NutritionAction.ASK, query=query, safe_message='unknown')
        food = self.egg if query == '鸡蛋' else self.rice
        return FoodSearchResult(action=NutritionAction.PASS, query=query, selected_food=food, safe_message='matched')

    def calculate_nutrition(self, request: object):
        from app.nutrition.schemas import NutritionAction, NutritionCalculationResult, NutritionValues

        food = self.egg if request.food_id == self.egg.id else self.rice
        self.calls.append(('calculate', str(food.id)))
        grams = request.grams
        if grams is None and request.portion_description is not None:
            portions = [portion for portion in food.portions if portion.description == request.portion_description and portion.audited]
            grams = portions[0].grams if len(portions) == 1 else None
        assert grams is not None
        factor = grams / Decimal('100')
        source = food.nutrients_per_100g
        return NutritionCalculationResult(
            action=NutritionAction.PASS, food=food, grams=grams,
            nutrients=NutritionValues(energy_kcal=source.energy_kcal * factor, protein_g=source.protein_g * factor, fat_g=source.fat_g * factor, carbohydrate_g=source.carbohydrate_g * factor),
            safe_message='calculated',
        )

    def validate_nutrition_result(self, request: object):
        from app.nutrition.schemas import NutritionAction, NutritionValidationResult

        self.calls.append(('validate', str(request.calculation.food.id)))
        return NutritionValidationResult(action=NutritionAction.PASS, rule_id='pass', safe_message='valid')


def _initial_state(message: str = 'test meal') -> object:
    from app.agent.state import MealAgentState

    return MealAgentState(
        user_id=uuid.uuid4(), thread_id=uuid.uuid4(), run_id=uuid.uuid4(), messages=(message,),
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


def test_real_agent_provider_tool_spans_are_allowlisted_and_parented() -> None:
    """A real graph path must produce the three allowed span classes, without payload data."""

    import httpx
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    from app.agent.graph import MealAnalysisGraph
    from app.agent.supervisor import PostgresLeaseSupervisor
    from app.core.tracing import TracedNutritionToolAdapter, create_tracing_runtime
    from app.providers.reasoning.deepseek import DeepSeekReasoningModelProvider

    exporter = InMemorySpanExporter()
    runtime = create_tracing_runtime(
        Settings(
            tracing_enabled=True,
            tracing_collector_endpoint="https://collector.example/v1/traces",
            tracing_hmac_key="trace-hmac-key",
            tracing_service_name="food-agent",
            tracing_service_version="v1",
            _env_file=None,
        ),
        exporter=exporter,
    )

    def completed_response(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": (
                                    '{"items":[{"item_id":"rice-1","food_name":"米饭",'
                                    '"catalog_query":"米饭","grams":"100"}]}'
                                ),
                            }
                        ],
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            },
        )

    provider = DeepSeekReasoningModelProvider(
        api_key="test-key",
        model="deepseek-v4-flash",
        timeout_seconds=20,
        price_snapshot={"input_usd_per_m": "1", "output_usd_per_m": "2"},
        transport=httpx.MockTransport(completed_response),
        tracing=runtime,
    )
    tools = TracedNutritionToolAdapter(delegate=_RecordingNutritionTools(), tracing=runtime)
    graph = MealAnalysisGraph(provider=provider, tools=tools)
    supervisor = PostgresLeaseSupervisor(
        session_factory=lambda: pytest.fail("test must not claim a database lease"),
        holder_id="trace-test",
        tracing=runtime,
    )

    asyncio.run(supervisor.start())
    state = _initial_state()
    with supervisor.run_span(
        thread_id=state.thread_id,
        graph_version=state.graph_version,
        prompt_version=state.prompt_version,
        tool_version=state.tool_version,
    ):
        result = asyncio.run(graph.ainvoke(state))
    asyncio.run(supervisor.stop())

    assert result.status.value == "completed"
    spans = exporter.get_finished_spans()
    by_name = {span.name: span for span in spans}
    assert set(by_name) == {
        "agent.run",
        "agent.provider",
        "nutrition.search_food_catalog",
        "nutrition.calculate_nutrition",
        "nutrition.validate_nutrition_result",
    }
    run = by_name["agent.run"]
    for name, span in by_name.items():
        if name == "agent.run":
            continue
        assert span.context.trace_id == run.context.trace_id
        assert span.parent is not None and span.parent.span_id == run.context.span_id
    forbidden = {"meal.text", "user.id", "prompt", "chain_of_thought", "input", "output"}
    for span in spans:
        attributes = dict(span.attributes or {})
        assert not forbidden & set(attributes)
        assert all("米饭" not in str(value) for value in attributes.values())


def test_disabled_tracing_has_no_exporter_side_effect() -> None:
    from app.core.tracing import create_tracing_runtime

    runtime = create_tracing_runtime(Settings(tracing_enabled=False, _env_file=None))
    with runtime.span("agent.run", {"node.name": "parse"}):
        pass
    runtime.flush()
    runtime.shutdown()
    assert runtime.scoped_hmac("thread-id") == "disabled"


def test_retention_config_fails_closed_in_production_and_bounds_scheduler() -> None:
    """D-18 retention is an explicit production contract, never a silent default."""

    from pydantic import ValidationError

    production = {
        "app_env": "production",
        "database_url": "postgresql+psycopg://db.example/food_agent",
        "secret_key": "x" * 32,
        "cookie_secure": True,
        "cors_origins": ["https://app.example"],
        "smtp_host": "smtp.example",
        "smtp_from_email": "noreply@example.com",
        "smtp_username": "mailer",
        "smtp_password": "password",
        "reasoning_provider_mode": "deepseek",
        "deepseek_api_key": "test-key",
        "deepseek_model": "deepseek-v4-flash",
        "deepseek_price_snapshot_version": "price-v1",
        "deepseek_input_usd_per_m": "1",
        "deepseek_output_usd_per_m": "2",
        "_env_file": None,
    }
    with pytest.raises(ValidationError, match="RETENTION_CHECKPOINT_EVENT_DAYS"):
        Settings(**production)

    with pytest.raises(ValidationError, match="RETENTION_POLL_INTERVAL_SECONDS"):
        Settings(
            **production,
            retention_checkpoint_event_days=7,
            retention_audit_days=30,
            retention_deletion_sla_hours=24,
            retention_poll_interval_seconds=301,
        )

    settings = Settings(
        app_env="test",
        database_url="postgresql+psycopg://postgres:postgres@localhost:5432/food_agent_dev",
        test_database_url="postgresql+psycopg://postgres:postgres@localhost:55432/food_agent_test",
        retention_checkpoint_event_days=7,
        retention_audit_days=30,
        retention_deletion_sla_hours=24,
        retention_poll_interval_seconds=300,
        _env_file=None,
    )
    assert settings.retention_deletion_due_delta.total_seconds() == 24 * 60 * 60 - 300


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


def test_graph_recovers_one_explicit_gram_value_omitted_by_provider() -> None:
    from app.providers.reasoning.dto import ParsedMealItemDTO

    graph, _provider, tools = _graph_with_items(
        ParsedMealItemDTO(item_id='rice-1', food_name='米饭', catalog_query='米饭')
    )

    completed = asyncio.run(graph.ainvoke(_initial_state('米饭100g')))

    assert completed.status.value == 'completed'
    assert completed.clarification_questions == ()
    assert completed.report is not None
    assert completed.report['totals']['energy_kcal'] == '130.0'
    assert tools.calls == [
        ('search', '米饭'),
        ('calculate', '11111111-1111-4111-8111-111111111111'),
        ('validate', '11111111-1111-4111-8111-111111111111'),
    ]


def test_graph_never_sends_an_internal_item_id_to_catalog_search() -> None:
    """A stale optional query must fall back to the actual normalized food name."""

    from app.providers.reasoning.dto import ParsedMealItemDTO

    graph, _provider, tools = _graph_with_items(
        ParsedMealItemDTO(
            item_id="item_1", food_name="米饭", catalog_query="item_1", grams=Decimal("100")
        )
    )

    completed = asyncio.run(graph.ainvoke(_initial_state("米饭 100g")))

    assert completed.status.value == "completed"
    assert tools.calls[0] == ("search", "米饭")


def test_graph_uses_an_audited_catalog_portion_without_hardcoding_its_name() -> None:
    from app.providers.reasoning.dto import ParsedMealItemDTO

    graph, _provider, _tools = _graph_with_items(
        ParsedMealItemDTO(item_id='rice-1', food_name='米饭', catalog_query='米饭')
    )

    completed = asyncio.run(graph.ainvoke(_initial_state('米饭一拳')))

    assert completed.status.value == 'completed'
    assert completed.items[0].grams == Decimal('120')
    assert completed.items[0].portion_description == '一拳'
    assert completed.report is not None
    assert completed.report['totals']['energy_kcal'] == '156.0'


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

    completed = asyncio.run(graph.ainvoke(waiting, resume={'answers': {'food-1': {'candidate_id': str(question.candidates[0].food_id), 'catalog_version': question.candidates[0].catalog_version}}}))
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
        ('search', '米饭'),
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
    readiness = client.get("/api/v1/ready")
    assert readiness.status_code == 503
    assert readiness.json() == {"status": "unavailable"}


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
    commits = []
    service = AgentService(repository=repository, now=lambda: now, commit=lambda: commits.append(True))

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

    assert len(commits) == 2  # Both the create and reuse paths release their row locks.
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


def test_lease_wait_does_not_block_event_loop() -> None:
    import threading
    from types import SimpleNamespace
    from app.agent.api import _execute

    released = threading.Event()
    entered = threading.Event()

    def claim(**kwargs):
        entered.set()
        assert released.wait(timeout=2), "lease blocked the event loop"
        return SimpleNamespace(holder_id="attempt-1")

    def release(**kwargs):
        assert kwargs["holder_id"] == "attempt-1"

    class Service:
        async def execute_run(self, **kwargs):
            return None

    async def scenario():
        runtime = SimpleNamespace(
            supervisor=SimpleNamespace(claim=claim, release=release),
            graph=SimpleNamespace(for_kind=lambda _kind: object()),
            checkpointer=None,
        )
        task = asyncio.create_task(_execute(service=Service(), runtime=runtime, run_id=uuid.uuid4(), user_id=uuid.uuid4()))
        try:
            while not entered.is_set():
                await asyncio.sleep(0)
            released.set()
            await task
        finally:
            released.set()

    asyncio.run(scenario())


def test_langfuse_tracing_uses_only_safe_metadata_and_closes_client() -> None:
    from app.core.tracing import create_tracing_runtime

    class FakeObservation:
        def __init__(self) -> None:
            self.updates: list[dict[str, object]] = []

        def __enter__(self) -> "FakeObservation":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def update(self, **payload: object) -> None:
            self.updates.append(payload)

    class FakeLangfuse:
        def __init__(self) -> None:
            self.observations: list[dict[str, object]] = []
            self.observation = FakeObservation()
            self.flushes = 0
            self.shutdowns = 0

        def start_as_current_observation(self, **payload: object) -> FakeObservation:
            self.observations.append(payload)
            return self.observation

        def flush(self) -> None:
            self.flushes += 1

        def shutdown(self) -> None:
            self.shutdowns += 1

    client = FakeLangfuse()
    runtime = create_tracing_runtime(
        Settings(
            _env_file=None,
            tracing_enabled=True,
            tracing_backend="langfuse",
            tracing_hmac_key="local-hmac",
            tracing_service_name="food-agent",
            tracing_service_version="dev",
            langfuse_public_key="pk-lf-test",
            langfuse_secret_key="sk-lf-test",
            langfuse_base_url="http://127.0.0.1:3001",
        ),
        langfuse_client=client,
    )

    with runtime.span(
        "agent.provider",
        {"provider.model": "deepseek-v4-flash", "prompt": "must-not-leak"},
    ) as span:
        span.update(
            input={"message": "米饭 test@example.com 13800138000", "api_key": "secret"},
            output={"food": "米饭", "reasoning_content": "hidden"},
            usage_details={"input": 10, "output": 5, "total": 15},
            cost_details={"total": 0.01},
        )
    runtime.flush()
    runtime.shutdown()

    assert client.observations == [
        {
            "name": "agent.provider",
            "as_type": "generation",
            "metadata": {
                "service.name": "food-agent",
                "service.version": "dev",
                "provider.model": "deepseek-v4-flash",
            },
            "model": "deepseek-v4-flash",
        }
    ]
    assert client.observation.updates == [
        {
            "input": {
                "message": "米饭 [email redacted] [phone redacted]",
                "api_key": "[redacted]",
            },
            "output": {"food": "米饭", "reasoning_content": "[redacted]"},
            "usage_details": {"input": 10, "output": 5, "total": 15},
            "cost_details": {"total": 0.01},
        }
    ]
    assert client.flushes == 1
    assert client.shutdowns == 1


def test_idempotent_run_lookup_checks_owner_and_payload_without_creating_work():
    from app.agent.models import AgentThread
    from app.agent.service import AgentCommandConflict, AgentService, AgentThreadUnavailable

    now = datetime(2026, 9, 16, tzinfo=UTC)
    owner, thread_id = uuid.uuid4(), uuid.uuid4()
    thread = AgentThread(id=thread_id, user_id=owner, status="open", revision=0,
                         created_at=now, last_activity_at=now, deleted_at=None)
    repository = _FakeAgentRepository(thread=thread)
    service = AgentService(repository=repository, now=lambda: now)
    arguments = dict(thread_id=thread_id, user_id=owner, command_key="submission-1",
                     canonical_command={"kind": "planning_adjustment", "input_hash": "digest"})
    assert service.find_reusable_run(**arguments) is None
    run = service.create_or_reuse_run(**arguments)
    for status in ("accepted", "running", "waiting_input", "completed", "failed", "limit_reached"):
        run.status = status
        assert service.find_reusable_run(**arguments) is run
    with pytest.raises(AgentCommandConflict):
        service.find_reusable_run(**(arguments | {"canonical_command": {"input_hash": "different"}}))
    with pytest.raises(AgentThreadUnavailable):
        service.find_reusable_run(**(arguments | {"user_id": uuid.uuid4()}))
    assert service.find_reusable_run(**(arguments | {"command_key": "submission-2"})) is None
    thread.deleted_at = now
    with pytest.raises(AgentThreadUnavailable):
        service.find_reusable_run(**arguments)
