"""Authenticated HTTP boundary for strict dashboard read projections."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from datetime import date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.api import AuthenticatedPrincipal
from app.core.config import get_settings
from app.core.database import get_session
from app.dashboard.repository import SqlAlchemyDashboardRepository
from app.dashboard.schemas import DashboardHistoryPage, DashboardOverview, WeeklyReviewPublicResponse
from app.dashboard.service import DashboardService, InvalidDashboardCursor, WeeklyReviewService, _facts_digest
from app.dashboard.weekly_review import run_weekly_review
from app.dashboard.weekly_review_dto import WeeklyReviewFacts
from app.dashboard.weekly_review_graph import WeeklyReviewGraph, WeeklyReviewGraphConfig
from app.planning.repository import SqlAlchemyPlanningProfileRepository
from app.providers.reasoning.factory import create_reasoning_provider


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


def get_weekly_review_service(session: SessionDependency) -> Generator[WeeklyReviewService, None, None]:
    """Compose facts cache and bounded graph below the HTTP boundary."""
    settings = get_settings()
    provider = create_reasoning_provider(settings)
    graph = WeeklyReviewGraph(
        provider=provider,
        config=WeeklyReviewGraphConfig(
            runtime_config_version="weekly-review-runtime.v1",
            provider_enabled=True,
        ),
    )

    def public_runner(facts: WeeklyReviewFacts):
        return asyncio.run(run_weekly_review(
            graph=graph,
            facts=_graph_facts(facts=facts, today=datetime.now().date()),
            facts_digest=_facts_digest(facts),
        ))

    repository = SqlAlchemyDashboardRepository(session)
    yield WeeklyReviewService(
        repository=repository,
        cache_repository=repository,
        provider=lambda _facts: "unused-legacy-provider",
        public_runner=public_runner,
        runtime_config_version="weekly-review-runtime.v1",
    )


WeeklyReviewServiceDependency = Annotated[WeeklyReviewService, Depends(get_weekly_review_service)]


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


@router.get("/weekly-review", operation_id="getWeeklyReview", response_model=WeeklyReviewPublicResponse)
def get_weekly_review(
    principal: AuthenticatedPrincipal,
    service: WeeklyReviewServiceDependency,
    week_start: date | None = Query(default=None),
) -> WeeklyReviewPublicResponse:
    _validate_week_start(week_start)
    return service.get_public_weekly_review(user_id=principal, week_start=week_start)


@router.post("/weekly-review/refresh", operation_id="refreshWeeklyReview", response_model=WeeklyReviewPublicResponse)
def refresh_weekly_review(
    principal: AuthenticatedPrincipal,
    service: WeeklyReviewServiceDependency,
    week_start: date | None = Query(default=None),
) -> WeeklyReviewPublicResponse:
    _validate_week_start(week_start)
    return service.get_public_weekly_review(user_id=principal, week_start=week_start, refresh=True)


def _validate_week_start(week_start: date | None) -> None:
    if week_start is None:
        return
    current_start = date.today() - timedelta(days=date.today().weekday())
    if week_start.weekday() != 0 or week_start > current_start:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="week_start must be a current or completed Monday.")


def _graph_facts(*, facts: WeeklyReviewFacts, today: date) -> dict[str, object]:
    """Only deterministic aggregates cross into the graph's de-identified DTO."""
    return {
        "facts_version": "weekly-review-facts.v1",
        "week_start": facts.week_start,
        "week_end_exclusive": facts.week_start + timedelta(days=7),
        "week_kind": "current_to_date" if facts.week_start + timedelta(days=6) >= today else "completed",
        "coverage_days": facts.coverage_days,
        "meal_count": facts.meal_count,
        "totals": {key: int(value) for key, value in facts.totals.model_dump().items()},
        "allowed_patterns": ["meal_regularity"],
        "coverage_sufficient": facts.coverage_days >= 4 and facts.meal_count >= 8,
    }
