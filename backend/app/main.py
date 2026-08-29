"""FastAPI application entry point."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.auth.api import router as auth_router, users_router
from app.admin.api import router as admin_router
from app.agent.api import router as agent_router
from app.agent.graph import AgentRuntime, AgentRuntimeFactory, MealAnalysisGraph
from app.agent.supervisor import PostgresLeaseSupervisor
from app.agent.tools import SessionNutritionToolAdapter
from app.accounts.api import router as account_recovery_router
from app.core.config import Settings, get_settings
from app.core.config import validate_test_database_configuration
from app.core.database import create_session_factory
from app.providers.reasoning.fake import RiceOnlyFakeReasoningModelProvider


class PersistedAgentRuntimeFactory:
    """Create all long-lived runtime resources once; setup remains a deployment CLI concern."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._saver_context: AbstractAsyncContextManager[Any] | None = None

    async def create(self) -> AgentRuntime:
        database_url = (
            validate_test_database_configuration(self._settings)
            if self._settings.app_env == "test"
            else self._settings.database_url
        )
        session_factory = create_session_factory(
            self._settings.model_copy(update={"database_url": database_url})
        )
        tools = SessionNutritionToolAdapter(session_factory=session_factory)
        provider = RiceOnlyFakeReasoningModelProvider()
        graph = MealAnalysisGraph(provider=provider, tools=tools)
        supervisor = PostgresLeaseSupervisor(
            session_factory=session_factory, holder_id="fastapi-agent-runtime"
        )
        await supervisor.start()
        # Checkpointer schema setup is intentionally performed by the explicit bootstrap CLI.
        # Lifespan only opens the already-initialized saver and gives its handle to the runtime.
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
        from sqlalchemy.engine import make_url

        conninfo = make_url(database_url).set(drivername="postgresql").render_as_string(
            hide_password=False
        )
        context = AsyncPostgresSaver.from_conn_string(
            conninfo,
            serde=JsonPlusSerializer(pickle_fallback=False, allowed_msgpack_modules=None),
        )
        self._saver_context = context
        checkpointer = await context.__aenter__()
        return AgentRuntime(
            graph=graph, tools=tools, checkpointer=checkpointer, supervisor=supervisor
        )

    async def close(self, runtime: AgentRuntime | None) -> None:
        if runtime is not None:
            await cast(PostgresLeaseSupervisor, runtime.supervisor).stop()
        if self._saver_context is not None:
            await self._saver_context.__aexit__(None, None, None)
            self._saver_context = None


@asynccontextmanager
async def _agent_lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Give later runtime wiring one lifecycle owner rather than per-request setup."""

    factory: AgentRuntimeFactory = application.state.agent_runtime_factory
    runtime = await factory.create()
    application.state.agent_runtime = runtime
    try:
        yield
    finally:
        await factory.close(runtime)


def create_app(
    settings: Settings | None = None, *, runtime_factory: AgentRuntimeFactory | None = None
) -> FastAPI:
    """Build the HTTP application from already validated runtime settings."""

    active_settings = settings or get_settings()
    application = FastAPI(
        title="Food Agent API",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=_agent_lifespan,
    )
    application.state.settings = active_settings
    application.state.agent_runtime_factory = runtime_factory or PersistedAgentRuntimeFactory(active_settings)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(auth_router)
    application.include_router(users_router)
    application.include_router(admin_router)
    application.include_router(account_recovery_router)
    application.include_router(agent_router)

    @application.exception_handler(RequestValidationError)
    async def validation_error(
        _request: Request, _error: RequestValidationError
    ) -> JSONResponse:
        # Raw Pydantic errors may contain submitted secrets; expose only a stable code.
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "请求字段不符合要求。",
                    "request_id": str(uuid.uuid4()),
                }
            },
        )

    @application.exception_handler(Exception)
    async def internal_error(_request: Request, _error: Exception) -> JSONResponse:
        # Provider/database exceptions stay server-side and never become response details.
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "服务暂时不可用，请稍后重试。",
                    "request_id": str(uuid.uuid4()),
                }
            },
        )

    @application.get("/api/v1/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok", "version": "v1"}

    return application


app = create_app()
