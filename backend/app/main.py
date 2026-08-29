"""FastAPI application entry point."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.auth.api import router as auth_router, users_router
from app.admin.api import router as admin_router
from app.agent.api import router as agent_router
from app.agent.graph import AgentRuntimeFactory, NoopAgentRuntimeFactory
from app.accounts.api import router as account_recovery_router
from app.core.config import Settings, get_settings


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
    application.state.agent_runtime_factory = runtime_factory or NoopAgentRuntimeFactory()
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
