"""Authenticated Agent API backed by a tenant-filtered event ledger.

Routes own HTTP presentation only. AgentService owns ownership/idempotency and the graph sees
only its provider/tool ports; SSE merely replays safe persisted events and never drives a run.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from collections.abc import Generator, Iterator
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, HTTPException, Request, Security, status
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials

from app.agent.graph import AgentRuntime
from app.agent.repository import SqlAlchemyAgentRepository
from app.agent.schemas import (
    AgentCommandAcceptedResponse,
    AgentDeletionAcceptedResponse,
    AgentErrorResponse,
    AgentInputRequest,
    AgentThreadCreateRequest,
    AgentThreadSnapshot,
    AgentThreadStatus,
)
from app.agent.service import AgentService, AgentThreadUnavailable
from app.agent.supervisor import PostgresLeaseSupervisor
from app.auth.api import bearer_scheme, get_authentication_service
from app.auth.security import InvalidAccessToken
from app.auth.service import AuthenticatedUserUnavailable, AuthenticationService

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])
_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"model": AgentErrorResponse, "description": "Bearer authentication failed."},
    status.HTTP_404_NOT_FOUND: {"model": AgentErrorResponse, "description": "Thread is unavailable."},
    status.HTTP_409_CONFLICT: {"model": AgentErrorResponse, "description": "Command conflicts."},
}


def get_agent_principal(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    service: AuthenticationService = Depends(get_authentication_service),
) -> uuid.UUID:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _authentication_required()
    try:
        user_id, _session_id = service.authenticated_session(credentials.credentials)
    except (InvalidAccessToken, AuthenticatedUserUnavailable):
        raise _authentication_required() from None
    return user_id


AgentPrincipal = Annotated[uuid.UUID, Depends(get_agent_principal)]


def _runtime(request: Request) -> AgentRuntime:
    runtime = cast(AgentRuntime | None, getattr(request.app.state, "agent_runtime", None))
    if runtime is None:
        raise HTTPException(status_code=503, detail="Agent runtime is unavailable.")
    return runtime


def get_agent_service(request: Request) -> Generator[AgentService, None, None]:
    """Use the lifecycle-selected DB target; test mode never falls back to DATABASE_URL."""

    session = cast(Any, _runtime(request).session_factory())
    try:
        yield AgentService(
            repository=SqlAlchemyAgentRepository(session), commit=session.commit, rollback=session.rollback
        )
    finally:
        session.close()


def _status(run_status: str | None) -> AgentThreadStatus:
    return {
        "accepted": AgentThreadStatus.PARTIAL, "running": AgentThreadStatus.PARTIAL,
        "waiting_input": AgentThreadStatus.WAITING, "completed": AgentThreadStatus.COMPLETED,
        "failed": AgentThreadStatus.RETRYABLE, "limit_reached": AgentThreadStatus.TERMINAL,
    }.get(run_status or "", AgentThreadStatus.PARTIAL)


def _snapshot(service: AgentService, *, thread_id: uuid.UUID, user_id: uuid.UUID) -> AgentThreadSnapshot:
    thread, run, events = service.latest_run_and_events(thread_id=thread_id, user_id=user_id)
    report: dict[str, object] | None = None
    for event in reversed(events):
        candidate = event.payload.get("report")
        if event.event_type == "completed" and isinstance(candidate, dict):
            report = candidate
            break
    return AgentThreadSnapshot(thread_id=thread.id, status=_status(run.status if run else None), revision=thread.revision, report=report)


def _command_hash(text: str) -> dict[str, object]:
    # Durable idempotency contains a digest, never a meal description.
    return {"kind": "description", "input_hash": hashlib.sha256(text.encode("utf-8")).hexdigest()}


def _execute(*, service: AgentService, runtime: AgentRuntime, run_id: uuid.UUID, user_id: uuid.UUID, text: str) -> None:
    cast(PostgresLeaseSupervisor, runtime.supervisor).claim(run_id=run_id, user_id=user_id)
    asyncio.run(service.execute_run(run_id=run_id, user_id=user_id, graph=runtime.graph, checkpointer=runtime.checkpointer, input_text=text))


@router.post("/threads", operation_id="createAgentThread", response_model=AgentThreadSnapshot, status_code=status.HTTP_201_CREATED, responses=_ERROR_RESPONSES)
def create_agent_thread(payload: AgentThreadCreateRequest, request: Request, principal: AgentPrincipal, service: AgentService = Depends(get_agent_service)) -> AgentThreadSnapshot:
    thread = service.create_thread(user_id=principal)
    run = service.create_or_reuse_run(thread_id=thread.id, user_id=principal, command_key=f"initial-{uuid.uuid4()}", canonical_command=_command_hash(payload.input_text))
    _execute(service=service, runtime=_runtime(request), run_id=run.id, user_id=principal, text=payload.input_text)
    return _snapshot(service, thread_id=thread.id, user_id=principal)


@router.post("/threads/{thread_id}/input", operation_id="submitAgentInput", response_model=AgentCommandAcceptedResponse, status_code=status.HTTP_202_ACCEPTED, responses=_ERROR_RESPONSES)
def submit_agent_input(thread_id: uuid.UUID, payload: AgentInputRequest, request: Request, principal: AgentPrincipal, service: AgentService = Depends(get_agent_service)) -> AgentCommandAcceptedResponse:
    try:
        run = service.create_or_reuse_run(thread_id=thread_id, user_id=principal, command_key=f"input-{uuid.uuid4()}", canonical_command=_command_hash(payload.text))
    except AgentThreadUnavailable:
        raise _unavailable() from None
    _execute(service=service, runtime=_runtime(request), run_id=run.id, user_id=principal, text=payload.text)
    return AgentCommandAcceptedResponse(thread_id=thread_id, status=_status(run.status))


@router.get("/threads/{thread_id}", operation_id="getAgentThread", response_model=AgentThreadSnapshot, responses=_ERROR_RESPONSES)
def get_agent_thread(thread_id: uuid.UUID, principal: AgentPrincipal, service: AgentService = Depends(get_agent_service)) -> AgentThreadSnapshot:
    try:
        return _snapshot(service, thread_id=thread_id, user_id=principal)
    except AgentThreadUnavailable:
        raise _unavailable() from None


@router.get("/threads/{thread_id}/events", operation_id="streamAgentEvents", response_model=None, responses={status.HTTP_200_OK: {"description": "Server-sent Agent events.", "content": {"text/event-stream": {"schema": {"type": "string"}}}}, **_ERROR_RESPONSES})
def stream_agent_events(thread_id: uuid.UUID, request: Request, principal: AgentPrincipal, service: AgentService = Depends(get_agent_service)) -> StreamingResponse:
    try:
        after_seq = max(int(request.headers.get("last-event-id", "0")), 0)
        _thread, _run, events = service.latest_run_and_events(thread_id=thread_id, user_id=principal, after_seq=after_seq)
    except (AgentThreadUnavailable, ValueError):
        raise _unavailable() from None

    def replay() -> Iterator[str]:
        for event in events:
            body = json.dumps({"type": event.event_type, "summary": event.safe_summary}, ensure_ascii=False)
            yield f"id: {event.seq}\nevent: agent\ndata: {body}\n\n"

    return StreamingResponse(replay(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@router.post("/threads/{thread_id}/retry", operation_id="retryAgentRun", response_model=AgentCommandAcceptedResponse, status_code=status.HTTP_202_ACCEPTED, responses=_ERROR_RESPONSES)
def retry_agent_run(thread_id: uuid.UUID, principal: AgentPrincipal) -> JSONResponse:
    _ = thread_id, principal
    return _error(status.HTTP_409_CONFLICT, "RETRY_REQUIRES_INPUT", "请重新提交餐食描述。")


@router.delete("/threads/{thread_id}", operation_id="deleteAgentThread", response_model=AgentDeletionAcceptedResponse, status_code=status.HTTP_202_ACCEPTED, responses=_ERROR_RESPONSES)
def delete_agent_thread(thread_id: uuid.UUID, principal: AgentPrincipal) -> JSONResponse:
    _ = thread_id, principal
    return _error(status.HTTP_409_CONFLICT, "DELETION_NOT_AVAILABLE", "删除任务尚未接通。")


def _authentication_required() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer authentication is required.", headers={"WWW-Authenticate": "Bearer"})


def _unavailable() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent thread is unavailable.")


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message, "request_id": str(uuid.uuid4())}})
