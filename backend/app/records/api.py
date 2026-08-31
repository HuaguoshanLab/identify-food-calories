"""Authenticated HTTP presentation for tenant-bound meal records."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agent.api import AgentPrincipal
from app.core.database import get_session
from app.records.repository import SqlAlchemyMealRecordRepository
from app.records.schemas import MealRecordConfirmRequest, MealRecordResponse, MealRecordUpdateRequest
from app.records.service import (
    ConsumedAtInvalid,
    MealRecordCommandConflict,
    MealRecordConfirmationUnavailable,
    MealRecordService,
    MealRecordUnavailable,
)


router = APIRouter(prefix="/api/v1/meal-records", tags=["meal-records"])
SessionDependency = Annotated[Session, Depends(get_session)]


def get_meal_record_service(session: SessionDependency) -> Generator[MealRecordService, None, None]:
    yield MealRecordService(
        repository=SqlAlchemyMealRecordRepository(session), commit=session.commit, rollback=session.rollback
    )


ServiceDependency = Annotated[MealRecordService, Depends(get_meal_record_service)]


@router.post("", operation_id="confirmMealRecord", response_model=MealRecordResponse, status_code=status.HTTP_201_CREATED)
def confirm_meal_record(
    payload: MealRecordConfirmRequest, principal: AgentPrincipal, service: ServiceDependency
) -> MealRecordResponse:
    try:
        return MealRecordResponse.model_validate(
            service.confirm_from_completed_run(
                user_id=principal, thread_id=payload.thread_id, command_key=payload.command_key, consumed_at=payload.consumed_at
            )
        )
    except ConsumedAtInvalid:
        raise _validation("consumed_at 必须是当前或过去的带时区时间。") from None
    except MealRecordConfirmationUnavailable:
        raise _unavailable() from None
    except MealRecordCommandConflict:
        raise _conflict("保存请求与原幂等键不匹配。") from None


@router.get("", operation_id="listMealRecords", response_model=list[MealRecordResponse])
def list_meal_records(principal: AgentPrincipal, service: ServiceDependency) -> list[MealRecordResponse]:
    return [MealRecordResponse.model_validate(record) for record in service.list_records(user_id=principal)]


@router.get("/{record_id}", operation_id="getMealRecord", response_model=MealRecordResponse)
def get_meal_record(record_id: uuid.UUID, principal: AgentPrincipal, service: ServiceDependency) -> MealRecordResponse:
    try:
        return MealRecordResponse.model_validate(service.get_record(record_id=record_id, user_id=principal))
    except MealRecordUnavailable:
        raise _unavailable() from None


@router.patch("/{record_id}", operation_id="updateMealRecord", response_model=MealRecordResponse)
def update_meal_record(
    record_id: uuid.UUID, payload: MealRecordUpdateRequest, principal: AgentPrincipal, service: ServiceDependency
) -> MealRecordResponse:
    try:
        return MealRecordResponse.model_validate(
            service.update_record(record_id=record_id, user_id=principal, consumed_at=payload.consumed_at)
        )
    except ConsumedAtInvalid:
        raise _validation("consumed_at 必须是当前或过去的带时区时间。") from None
    except MealRecordUnavailable:
        raise _unavailable() from None


@router.delete("/{record_id}", operation_id="deleteMealRecord", status_code=status.HTTP_204_NO_CONTENT)
def delete_meal_record(record_id: uuid.UUID, principal: AgentPrincipal, service: ServiceDependency) -> None:
    try:
        service.delete_record(record_id=record_id, user_id=principal)
    except MealRecordUnavailable:
        raise _unavailable() from None


def _unavailable() -> HTTPException:
    # Owner and existence intentionally share one result, so UUIDs cannot be used as an oracle.
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal record is unavailable.")


def _validation(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message)


def _conflict(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)
