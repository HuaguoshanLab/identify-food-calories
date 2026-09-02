"""Authenticated HTTP boundary for strict dashboard read projections."""

from __future__ import annotations

from collections.abc import Generator
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.api import AuthenticatedPrincipal
from app.core.config import get_settings
from app.core.database import get_session
from app.dashboard.repository import SqlAlchemyDashboardRepository
from app.dashboard.schemas import DashboardHistoryPage, DashboardOverview
from app.dashboard.service import DashboardService, InvalidDashboardCursor
from app.planning.repository import SqlAlchemyPlanningProfileRepository


router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])
SessionDependency = Annotated[Session, Depends(get_session)]


def get_dashboard_service(session: SessionDependency) -> Generator[DashboardService, None, None]:
    """Composition injects the planning-owned narrow reader, never a profile into dashboard code."""
    yield DashboardService(
        repository=SqlAlchemyDashboardRepository(session),
        target_port=SqlAlchemyPlanningProfileRepository(session),
        cursor_secret=get_settings().secret_key.get_secret_value(),
    )


ServiceDependency = Annotated[DashboardService, Depends(get_dashboard_service)]


@router.get(
    "/overview", operation_id="getDashboardOverview", response_model=DashboardOverview,
    response_model_exclude_none=True,
)
def get_overview(
    principal: AuthenticatedPrincipal, service: ServiceDependency, week_start: date | None = None
) -> DashboardOverview:
    return service.get_overview(user_id=principal, week_start=week_start)


@router.get(
    "/history", operation_id="getDashboardHistory", response_model=DashboardHistoryPage,
    response_model_exclude_none=True,
)
def get_history(
    principal: AuthenticatedPrincipal,
    service: ServiceDependency,
    cursor: str | None = Query(default=None, min_length=1, max_length=1024),
    limit: int = Query(default=20, ge=1, le=50),
) -> DashboardHistoryPage:
    try:
        return service.get_history(user_id=principal, cursor=cursor, limit=limit)
    except InvalidDashboardCursor:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Dashboard cursor is invalid.") from None
