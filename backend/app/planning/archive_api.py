"""Authenticated saved-plan reads and deletion; no client-provided nutrition writes."""

import uuid
from collections.abc import Generator
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.api import AuthenticatedPrincipal
from app.core.database import get_session
from app.planning.archive_repository import SqlAlchemyPlanArchiveRepository
from app.planning.archive_schemas import PlanHistoryPage, SavedPlan, TodayPlan
from app.planning.archive_service import PlanArchiveService, PlanUnavailable

router = APIRouter(prefix="/api/v1/planning/plans", tags=["saved-plans"])


def get_plan_archive_service(
    session: Annotated[Session, Depends(get_session)],
) -> Generator[PlanArchiveService, None, None]:
    yield PlanArchiveService(
        repository=SqlAlchemyPlanArchiveRepository(session),
        commit=session.commit,
        rollback=session.rollback,
    )


Service = Annotated[PlanArchiveService, Depends(get_plan_archive_service)]


@router.get("/today", response_model=TodayPlan)
def today(principal: AuthenticatedPrincipal, service: Service) -> TodayPlan:
    return service.today(principal)


@router.get("", response_model=PlanHistoryPage)
def history(
    principal: AuthenticatedPrincipal,
    service: Service,
    before: date | None = None,
    limit: int = Query(default=20, ge=1, le=50),
) -> PlanHistoryPage:
    return service.history(principal, before, limit)


@router.get("/{plan_id}", response_model=SavedPlan)
def detail(
    plan_id: uuid.UUID,
    principal: AuthenticatedPrincipal,
    service: Service,
    version: int | None = Query(default=None, ge=1),
) -> SavedPlan:
    try:
        return service.detail(principal, plan_id, version)
    except PlanUnavailable:
        raise HTTPException(status_code=404, detail="Plan is unavailable.") from None


@router.delete("/{plan_id}", status_code=204)
def delete(
    plan_id: uuid.UUID, principal: AuthenticatedPrincipal, service: Service
) -> None:
    try:
        service.delete(principal, plan_id)
    except PlanUnavailable:
        raise HTTPException(status_code=404, detail="Plan is unavailable.") from None
