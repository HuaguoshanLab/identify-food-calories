"""Public Agent API contract; execution is intentionally deferred to later plans."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials

from app.agent.schemas import (
    AgentCommandAcceptedResponse,
    AgentDeletionAcceptedResponse,
    AgentErrorResponse,
    AgentInputRequest,
    AgentThreadCreateRequest,
    AgentThreadSnapshot,
)
from app.auth.api import bearer_scheme, get_authentication_service
from app.auth.security import InvalidAccessToken
from app.auth.service import AuthenticatedUserUnavailable, AuthenticationService


router = APIRouter(prefix="/api/v1/agent", tags=["agent"])

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"model": AgentErrorResponse, "description": "Bearer authentication failed."},
    status.HTTP_501_NOT_IMPLEMENTED: {"model": AgentErrorResponse, "description": "Operation declared before runtime implementation."},
}


def get_agent_principal(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    service: AuthenticationService = Depends(get_authentication_service),
) -> uuid.UUID:
    """Use the same access-token/session validation path as the authenticated H5."""

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _authentication_required()
    try:
        user_id, _session_id = service.authenticated_session(credentials.credentials)
    except (InvalidAccessToken, AuthenticatedUserUnavailable):
        raise _authentication_required() from None
    return user_id


AgentPrincipal = Annotated[uuid.UUID, Depends(get_agent_principal)]


@router.post(
    "/threads",
    operation_id="createAgentThread",
    response_model=AgentThreadSnapshot,
    status_code=status.HTTP_201_CREATED,
    responses=_ERROR_RESPONSES,
)
def create_agent_thread(
    _payload: AgentThreadCreateRequest, _principal: AgentPrincipal
) -> JSONResponse:
    return _not_implemented()


@router.post(
    "/threads/{thread_id}/input",
    operation_id="submitAgentInput",
    response_model=AgentCommandAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses=_ERROR_RESPONSES,
)
def submit_agent_input(
    thread_id: uuid.UUID, _payload: AgentInputRequest, _principal: AgentPrincipal
) -> JSONResponse:
    _ = thread_id
    return _not_implemented()


@router.get(
    "/threads/{thread_id}",
    operation_id="getAgentThread",
    response_model=AgentThreadSnapshot,
    responses=_ERROR_RESPONSES,
)
def get_agent_thread(thread_id: uuid.UUID, _principal: AgentPrincipal) -> JSONResponse:
    _ = thread_id
    return _not_implemented()


@router.get(
    "/threads/{thread_id}/events",
    operation_id="streamAgentEvents",
    response_model=None,
    responses={
        status.HTTP_200_OK: {
            "description": "Server-sent Agent events.",
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        },
        **_ERROR_RESPONSES,
    },
)
def stream_agent_events(thread_id: uuid.UUID, _principal: AgentPrincipal) -> JSONResponse:
    _ = thread_id
    return _not_implemented()


@router.post(
    "/threads/{thread_id}/retry",
    operation_id="retryAgentRun",
    response_model=AgentCommandAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses=_ERROR_RESPONSES,
)
def retry_agent_run(thread_id: uuid.UUID, _principal: AgentPrincipal) -> JSONResponse:
    _ = thread_id
    return _not_implemented()


@router.delete(
    "/threads/{thread_id}",
    operation_id="deleteAgentThread",
    response_model=AgentDeletionAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses=_ERROR_RESPONSES,
)
def delete_agent_thread(thread_id: uuid.UUID, _principal: AgentPrincipal) -> JSONResponse:
    _ = thread_id
    return _not_implemented()


def _authentication_required() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Bearer authentication is required.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _not_implemented() -> JSONResponse:
    """Prevent an apparently successful API before ownership/runtime exists."""

    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={
            "error": {
                "code": "AGENT_NOT_IMPLEMENTED",
                "message": "Agent runtime is not available yet.",
                "request_id": str(uuid.uuid4()),
            }
        },
    )
