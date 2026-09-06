"""Authenticated HTTP presentation for tenant-bound meal records."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.api import AuthenticatedPrincipal
from app.core.database import get_session
from app.records.repository import SqlAlchemyMealRecordRepository
from app.records.schemas import (
    DashboardTimezoneConfirmationRequest,
    DashboardTimezoneConfirmationResponse,
    MealRecordConfirmRequest,
    MealRecordResponse,
    MealRecordUpdateRequest,
)
from app.records.service import (
    ConsumedAtInvalid,
    DashboardTimeZoneAlreadyConfirmed,
    InvalidTimeZone,
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
    payload: MealRecordConfirmRequest, principal: AuthenticatedPrincipal, service: ServiceDependency
) -> MealRecordResponse:
    try:
        return MealRecordResponse.model_validate(
            service.confirm_from_completed_run(
                user_id=principal, thread_id=payload.thread_id, command_key=payload.command_key,
                consumed_at=payload.consumed_at, time_zone=payload.time_zone, meal_slot=payload.meal_slot,
            )
        )
    except InvalidTimeZone:
        raise _bad_request("time_zone 必须是有效的 IANA 时区。") from None
    except ConsumedAtInvalid:
        raise _validation("consumed_at 必须是当前或过去的带时区时间。") from None
    except MealRecordConfirmationUnavailable:
        raise _unavailable() from None
    except MealRecordCommandConflict:
        raise _conflict("保存请求与原幂等键不匹配。") from None


@router.get("", operation_id="listMealRecords", response_model=list[MealRecordResponse])
def list_meal_records(principal: AuthenticatedPrincipal, service: ServiceDependency) -> list[MealRecordResponse]:
    return [MealRecordResponse.model_validate(record) for record in service.list_records(user_id=principal)]


@router.post(
    "/dashboard-time-zone-confirmations",
    operation_id="confirmDashboardTimeZone",
    response_model=DashboardTimezoneConfirmationResponse,
)
def confirm_dashboard_time_zone(
    payload: DashboardTimezoneConfirmationRequest, principal: AuthenticatedPrincipal, service: ServiceDependency
) -> DashboardTimezoneConfirmationResponse:
    try:
        return service.confirm_dashboard_time_zone(user_id=principal, time_zone=payload.time_zone)
    except InvalidTimeZone:
        raise _bad_request("time_zone 必须是有效的 IANA 时区。") from None
    except DashboardTimeZoneAlreadyConfirmed:
        raise _conflict("统计时区已经确认，不能再次回填历史记录。") from None


@router.get("/{record_id}", operation_id="getMealRecord", response_model=MealRecordResponse)
def get_meal_record(record_id: uuid.UUID, principal: AuthenticatedPrincipal, service: ServiceDependency) -> MealRecordResponse:
    try:
        return MealRecordResponse.model_validate(service.get_record(record_id=record_id, user_id=principal))
    except MealRecordUnavailable:
        raise _unavailable() from None


@router.patch("/{record_id}", operation_id="updateMealRecord", response_model=MealRecordResponse)
def update_meal_record(
    record_id: uuid.UUID, payload: MealRecordUpdateRequest, principal: AuthenticatedPrincipal, service: ServiceDependency
) -> MealRecordResponse:
    try:
        return MealRecordResponse.model_validate(
            service.update_record(
                record_id=record_id, user_id=principal, consumed_at=payload.consumed_at,
                time_zone=payload.time_zone, meal_slot=payload.meal_slot,
                update_meal_slot="meal_slot" in payload.model_fields_set,
            )
        )
    except InvalidTimeZone:
        raise _bad_request("time_zone 必须是有效的 IANA 时区。") from None
    except ConsumedAtInvalid:
        raise _validation("consumed_at 必须是当前或过去的带时区时间。") from None
    except MealRecordUnavailable:
        raise _unavailable() from None


@router.delete("/{record_id}", operation_id="deleteMealRecord", status_code=status.HTTP_204_NO_CONTENT)
def delete_meal_record(record_id: uuid.UUID, principal: AuthenticatedPrincipal, service: ServiceDependency) -> None:
    try:
        service.delete_record(record_id=record_id, user_id=principal)
    except MealRecordUnavailable:
        raise _unavailable() from None


def _unavailable() -> HTTPException:
    # Owner and existence intentionally share one result, so UUIDs cannot be used as an oracle.
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meal record is unavailable.")


def _validation(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=message)


def _bad_request(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


def _conflict(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)
