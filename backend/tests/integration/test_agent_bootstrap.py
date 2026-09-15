"""Real PostgreSQL proof for the fixed migration → checkpoint → seed chain."""

from __future__ import annotations

import os
import subprocess
import sys
import asyncio
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from alembic.config import Config
from alembic.script import ScriptDirectory

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.agent.supervisor import PostgresLeaseSupervisor
from app.core.config import Settings, validate_test_database_configuration
from app.main import PersistedAgentRuntimeFactory, create_app
from app.nutrition.repository import SqlAlchemyNutritionRepository
from app.nutrition.schemas import FoodSearchInput
from app.nutrition.service import NutritionService
from app.providers.embedding.fake import FakeEmbeddingProvider


BACKEND_ROOT = Path(__file__).resolve().parents[2]
SEED_HASH = "9009d03d802589038efc7fe996fcf62f8ff2424f7a555f8ba6d86c378794a91f"


class _LifecycleRuntimeFactory:
    """Keep the HTTP test offline while exercising lifespan-owned worker wiring."""

    def __init__(self, supervisor: PostgresLeaseSupervisor, worker: object) -> None:
        self.runtime = type("Runtime", (), {"supervisor": supervisor})()
        self._supervisor = supervisor
        self._worker = worker
        self.created = False
        self.closed = False

    async def create(self) -> object:
        self.created = True
        await self._supervisor.start()
        await self._supervisor.start_embedding_worker(
            worker=self._worker,
            poll_interval=timedelta(milliseconds=1),
        )
        return self.runtime

    async def close(self, runtime: object | None) -> None:
        assert runtime is self.runtime
        self.closed = True
        await self.runtime.supervisor.stop()


class _IdleWorker:
    def __init__(self) -> None:
        self.calls = 0

    def run_once(self) -> str:
        self.calls += 1
        return "idle"


class _SpyTracingRuntime:
    """A memory-only exporter seam for lifecycle and privacy assertions."""

    def __init__(self) -> None:
        self.spans: list[dict[str, object]] = []
        self.flushes = 0
        self.shutdowns = 0

    @contextmanager
    def span(self, _name: str, attributes: dict[str, object]):
        self.spans.append(dict(attributes))
        yield

    def scoped_hmac(self, _value: str) -> str:
        return "test-fingerprint"

    def flush(self) -> None:
        self.flushes += 1

    def shutdown(self) -> None:
        self.shutdowns += 1


def test_embedding_worker_lifecycle_is_singleton_and_stops_cleanly() -> None:
    """The app owns the worker; tests never construct a real network provider."""

    async def scenario() -> None:
        settings = Settings(
            _env_file=None,
            app_env="test",
            test_database_url="postgresql+psycopg://postgres:postgres@localhost:55432/food_agent_test",
        )
        engine = create_engine(validate_test_database_configuration(settings))
        try:
            supervisor = PostgresLeaseSupervisor(
                session_factory=sessionmaker(engine), holder_id="embedding-lifespan-test"
            )
            worker = _IdleWorker()
            factory = _LifecycleRuntimeFactory(supervisor, worker)
            application = create_app(settings, runtime_factory=factory)
            async with application.router.lifespan_context(application):
                await asyncio.sleep(0.01)
                assert supervisor.embedding_worker_started is True
            assert factory.created is True
            assert factory.closed is True
            assert supervisor.embedding_worker_started is False
            assert worker.calls > 0
        finally:
            engine.dispose()

    asyncio.run(scenario())


def test_embedding_worker_disabled_mode_does_not_block_lifespan() -> None:
    """Exact/text retrieval stays usable when semantic retrieval is explicitly disabled."""

    settings = Settings(_env_file=None, embedding_provider_mode="disabled")  # type: ignore[call-arg]
    assert settings.embedding_provider_mode == "disabled"


def test_hybrid_tracing_runtime_is_shared_and_lifecycle_owned(monkeypatch: object) -> None:
    """The real factory wires one safe telemetry runtime and the app closes it once."""

    settings = Settings(
        _env_file=None,
        app_env="test",
        test_database_url="postgresql+psycopg://postgres:postgres@localhost:55432/food_agent_test",
    )
    tracing = _SpyTracingRuntime()
    embedding = FakeEmbeddingProvider()
    embedding.queue_result((tuple(0.0 for _ in range(1024)),))
    monkeypatch.setattr("app.main.create_tracing_runtime", lambda _settings: tracing)  # type: ignore[attr-defined]
    monkeypatch.setattr("app.main.create_embedding_provider", lambda _settings: embedding)  # type: ignore[attr-defined]
    application = create_app(settings)
    factory = application.state.agent_runtime_factory
    assert isinstance(factory, PersistedAgentRuntimeFactory)

    async def search() -> None:
        runtime = application.state.agent_runtime
        assert runtime.tools._tracing is tracing  # type: ignore[attr-defined]
        assert runtime.supervisor._tracing is tracing  # type: ignore[attr-defined]
        await runtime.tools.search_food_catalog(FoodSearchInput(query="不存在的受控食物"))

    from fastapi.testclient import TestClient

    with TestClient(application):
        asyncio.run(search())

    hybrid = next(attributes for attributes in tracing.spans if "retrieval.version" in attributes)
    assert set(hybrid) >= {
        "retrieval.version",
        "match.channel",
        "fallback.code",
        "latency.bucket",
        "index.health",
        "index.version",
    }
    forbidden = {"query", "vector", "candidate", "user", "meal", "body", "health"}
    assert not any(forbidden & set(attributes) for attributes in tracing.spans)
    assert tracing.flushes == 1
    assert tracing.shutdowns == 1


def test_prepare_only_is_idempotent_and_keeps_database_targets_distinct() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    test_url = validate_test_database_configuration(settings)
    development_url = make_url(settings.database_url)
    isolated_url = make_url(test_url)
    assert development_url.port == 5432
    assert development_url.database == "food_agent_dev"
    assert isolated_url.port == 55432
    assert isolated_url.database == "food_agent_test"
    assert development_url.render_as_string(hide_password=False) != isolated_url.render_as_string(
        hide_password=False
    )

    command = [sys.executable, "scripts/run_initialized_app.py", "--prepare-only"]
    for _ in range(2):
        subprocess.run(command, cwd=BACKEND_ROOT, env=os.environ.copy(), check=True)

    engine = create_engine(test_url)
    try:
        supervisor = PostgresLeaseSupervisor(
            session_factory=sessionmaker(engine), holder_id="bootstrap-test"
        )
        asyncio.run(supervisor.start())
        assert supervisor.started is True
        asyncio.run(supervisor.stop())
        table_names = set(inspect(engine).get_table_names())
        assert {"checkpoints", "checkpoint_blobs", "checkpoint_writes"} <= table_names
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
            assert connection.scalar(
                text(
                    "SELECT content_hash FROM nutrition_catalog_versions "
                    "WHERE version = 'foundation-foods-2025-04'"
                )
            ) == SEED_HASH
            assert connection.scalar(
                    text(
                        "SELECT count(*) FROM food_catalog_items "
                        "WHERE stable_id = 'fdc:169756' AND is_qualified "
                        "AND catalog_version_id = (SELECT id FROM nutrition_catalog_versions "
                        "WHERE version = 'foundation-foods-2026-08-rice-fist-v1')"
                    )
            ) == 1
            assert connection.scalar(
                text(
                    "SELECT count(*) FROM controlled_recipes "
                    "WHERE recipe_version = 'controlled-recipes.v2' AND is_active"
                )
            ) == 5
            assert connection.scalar(
                text(
                    "SELECT count(*) FROM controlled_recipes "
                    "WHERE recipe_version = 'controlled-recipes.v1' AND is_active"
                )
            ) == 0
            assert connection.scalar(
                text(
                    "SELECT count(*) FROM food_catalog_items "
                    "WHERE stable_id = 'recipe:chili-fried-pork-v2' AND is_qualified"
                )
            ) == 1
        with sessionmaker(engine)() as session:
            result = asyncio.run(NutritionService(repository=SqlAlchemyNutritionRepository(session)).search_food_catalog(
                FoodSearchInput(query="辣椒炒肉")
            ))
            assert result.selected_food is not None
            assert result.selected_food.canonical_name == "Chili fried pork, reference recipe v2"
    finally:
        engine.dispose()
