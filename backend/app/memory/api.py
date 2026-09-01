"""Bearer-protected memory management API; local ledger remains the authorization gate."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.api import AuthenticatedPrincipal
from app.core.config import Settings
from app.core.database import get_session
from app.memory.providers import create_memory_provider
from app.memory.repository import SqlAlchemyMemoryLedgerRepository
from app.memory.schemas import MemoryCreateRequest, MemoryResponse, MemoryUpdateRequest
from app.memory.service import MemoryService, MemoryUnavailable, MemoryValidationError
from app.agent.supervisor import PostgresLeaseSupervisor


router = APIRouter(prefix="/api/v1/memories", tags=["memories"])
SessionDependency = Annotated[Session, Depends(get_session)]


def get_memory_service(request: Request, session: SessionDependency) -> Generator[MemoryService, None, None]:
    settings = cast(Settings, request.app.state.settings)
    yield MemoryService(
        repository=SqlAlchemyMemoryLedgerRepository(session), provider=create_memory_provider(settings),
        commit=session.commit, rollback=session.rollback,
        retry_max_attempts=settings.memory_retry_max_attempts, retry_backoff_seconds=settings.memory_retry_backoff_seconds,
    )


ServiceDependency = Annotated[MemoryService, Depends(get_memory_service)]


@router.post("", operation_id="createDirectMemory", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
def create_direct_memory(payload: MemoryCreateRequest, principal: AuthenticatedPrincipal, service: ServiceDependency) -> MemoryResponse:
    try:
        return MemoryResponse.model_validate(service.create_direct(user_id=principal, category=payload.category, canonical_text=payload.canonical_text))
    except MemoryValidationError:
        raise _validation() from None


@router.post("/{memory_id}/confirm", operation_id="confirmInferredMemory", response_model=MemoryResponse)
def confirm_inferred_memory(memory_id: uuid.UUID, principal: AuthenticatedPrincipal, service: ServiceDependency) -> MemoryResponse:
    try:
        return MemoryResponse.model_validate(service.confirm_inference(memory_id=memory_id, user_id=principal))
    except MemoryUnavailable:
        raise _unavailable() from None


@router.get("", operation_id="listMemories", response_model=list[MemoryResponse])
def list_memories(principal: AuthenticatedPrincipal, service: ServiceDependency) -> list[MemoryResponse]:
    return [MemoryResponse.model_validate(memory) for memory in service.list_memories(user_id=principal)]


@router.get("/{memory_id}", operation_id="getMemory", response_model=MemoryResponse)
def get_memory(memory_id: uuid.UUID, principal: AuthenticatedPrincipal, service: ServiceDependency) -> MemoryResponse:
    try:
        return MemoryResponse.model_validate(service.get_memory(memory_id=memory_id, user_id=principal))
    except MemoryUnavailable:
        raise _unavailable() from None


@router.patch("/{memory_id}", operation_id="updateMemory", response_model=MemoryResponse)
def update_memory(memory_id: uuid.UUID, payload: MemoryUpdateRequest, principal: AuthenticatedPrincipal, service: ServiceDependency) -> MemoryResponse:
    try:
        return MemoryResponse.model_validate(service.update_memory(memory_id=memory_id, user_id=principal, canonical_text=payload.canonical_text))
    except MemoryUnavailable:
        raise _unavailable() from None
    except MemoryValidationError:
        raise _validation() from None


@router.delete("/{memory_id}", operation_id="deleteMemory", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(memory_id: uuid.UUID, request: Request, principal: AuthenticatedPrincipal, service: ServiceDependency) -> None:
    try:
        service.delete_memory(memory_id=memory_id, user_id=principal)
    except MemoryUnavailable:
        raise _unavailable() from None
    runtime = getattr(request.app.state, "agent_runtime", None)
    worker = getattr(getattr(runtime, "supervisor", None), "retention_worker", None)
    if isinstance(getattr(runtime, "supervisor", None), PostgresLeaseSupervisor) and worker is not None:
        worker.wake()


def _unavailable() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory is unavailable.")


def _validation() -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Memory fields are invalid.")
