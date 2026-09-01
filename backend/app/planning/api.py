"""Authenticated HTTP presentation for explicitly saved, minimal planning profiles."""

from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.api import AuthenticatedPrincipal
from app.core.database import get_session
from app.planning.repository import SqlAlchemyPlanningProfileRepository
from app.planning.schemas import PlanningProfilePatch, PlanningProfileResponse, PlanningProfileWrite
from app.planning.service import PlanningProfileService, PlanningProfileUnavailable


router = APIRouter(prefix="/api/v1/planning/profile", tags=["planning-profile"])
SessionDependency = Annotated[Session, Depends(get_session)]


def get_planning_profile_service(session: SessionDependency) -> Generator[PlanningProfileService, None, None]:
    yield PlanningProfileService(repository=SqlAlchemyPlanningProfileRepository(session), commit=session.commit, rollback=session.rollback)


ServiceDependency = Annotated[PlanningProfileService, Depends(get_planning_profile_service)]


@router.get("", operation_id="getPlanningProfile", response_model=PlanningProfileResponse)
def get_planning_profile(principal: AuthenticatedPrincipal, service: ServiceDependency) -> PlanningProfileResponse:
    try:
        return PlanningProfileResponse.model_validate(service.get_profile(user_id=principal))
    except PlanningProfileUnavailable:
        raise _unavailable() from None


@router.put("", operation_id="replacePlanningProfile", response_model=PlanningProfileResponse)
def replace_planning_profile(payload: PlanningProfileWrite, principal: AuthenticatedPrincipal, service: ServiceDependency) -> PlanningProfileResponse:
    return PlanningProfileResponse.model_validate(service.replace_profile(user_id=principal, payload=payload))


@router.patch("", operation_id="updatePlanningProfile", response_model=PlanningProfileResponse)
def update_planning_profile(payload: PlanningProfilePatch, principal: AuthenticatedPrincipal, service: ServiceDependency) -> PlanningProfileResponse:
    try:
        return PlanningProfileResponse.model_validate(service.update_profile(user_id=principal, payload=payload))
    except PlanningProfileUnavailable:
        raise _unavailable() from None


@router.delete("", operation_id="deletePlanningProfile", status_code=status.HTTP_204_NO_CONTENT)
def delete_planning_profile(principal: AuthenticatedPrincipal, service: ServiceDependency) -> None:
    try:
        service.delete_profile(user_id=principal)
    except PlanningProfileUnavailable:
        raise _unavailable() from None


def _unavailable() -> HTTPException:
    # Missing, foreign, and soft-deleted profiles intentionally share one observable result.
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Planning profile is unavailable.")
