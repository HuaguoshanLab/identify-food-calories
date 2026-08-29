"""Public runtime contract for the application foundation."""

from __future__ import annotations

import ast
import inspect
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings


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
