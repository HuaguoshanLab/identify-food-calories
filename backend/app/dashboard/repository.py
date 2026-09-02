"""Tenant-filtered SQL projections for persisted meal snapshots."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import cast

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.dashboard.models import WeeklyReviewResult
from app.dashboard.schemas import DashboardHistoryCursor, DashboardHistoryRecord, DashboardNutritionTotals
from app.dashboard.weekly_review_dto import WeeklyReviewCacheKey
from app.records.models import MealRecord


@dataclass(frozen=True)
class DashboardDailyAggregate:
    consumed_local_date: date
    totals: DashboardNutritionTotals
    meal_count: int


class SqlAlchemyDashboardRepository:
    """Every aggregate starts with tenant, active-row, and persisted-local-date predicates."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_daily_aggregates(
        self, *, user_id: uuid.UUID, start_date: date, end_date: date
    ) -> list[DashboardDailyAggregate]:
        statement = (
            select(
                MealRecord.consumed_local_date,
                func.sum(MealRecord.energy_kcal),
                func.sum(MealRecord.protein_g),
                func.sum(MealRecord.fat_g),
                func.sum(MealRecord.carbohydrate_g),
                func.count(MealRecord.id),
            )
            .where(
                MealRecord.user_id == user_id,
                MealRecord.deleted_at.is_(None),
                MealRecord.consumed_local_date.is_not(None),
                MealRecord.consumed_local_date.between(start_date, end_date),
            )
            .group_by(MealRecord.consumed_local_date)
            .order_by(MealRecord.consumed_local_date.asc())
        )
        return [
            DashboardDailyAggregate(
                consumed_local_date=local_date,
                totals=DashboardNutritionTotals(
                    energy_kcal=Decimal(energy_kcal), protein_g=Decimal(protein_g), fat_g=Decimal(fat_g), carbohydrate_g=Decimal(carbohydrate_g)
                ),
                meal_count=int(meal_count),
            )
            for local_date, energy_kcal, protein_g, fat_g, carbohydrate_g, meal_count in self._session.execute(statement)
        ]

    def get_history_page(
        self, *, user_id: uuid.UUID, cursor: DashboardHistoryCursor | None, limit: int
    ) -> list[DashboardHistoryRecord]:
        statement = self._active_local_record_statement(user_id=user_id)
        if cursor is not None:
            statement = statement.where(
                or_(
                    MealRecord.consumed_local_date < cursor.consumed_local_date,
                    and_(
                        MealRecord.consumed_local_date == cursor.consumed_local_date,
                        MealRecord.consumed_at < cursor.consumed_at,
                    ),
                    and_(
                        MealRecord.consumed_local_date == cursor.consumed_local_date,
                        MealRecord.consumed_at == cursor.consumed_at,
                        MealRecord.id < cursor.record_id,
                    ),
                )
            )
        rows = list(
            self._session.scalars(
                statement.order_by(
                    MealRecord.consumed_local_date.desc(), MealRecord.consumed_at.desc(), MealRecord.id.desc()
                ).limit(limit)
            )
        )
        # The SQL predicate excludes NULL local dates, so this narrowed view is safe for cursor construction.
        return [cast(DashboardHistoryRecord, row) for row in rows]

    def get_completed_weekly_review(self, *, key: WeeklyReviewCacheKey) -> WeeklyReviewResult | None:
        """Only terminal safe outcomes are reusable; running and unknown outcomes never replay."""
        return self._session.scalar(select(WeeklyReviewResult).where(
            WeeklyReviewResult.user_id == key.user_id, WeeklyReviewResult.week_start == key.week_start,
            WeeklyReviewResult.facts_digest == key.facts_digest, WeeklyReviewResult.graph_version == key.graph_version,
            WeeklyReviewResult.prompt_version == key.prompt_version, WeeklyReviewResult.schema_version == key.schema_version,
            WeeklyReviewResult.runtime_config_version == key.runtime_config_version, WeeklyReviewResult.status == "completed",
        ))

    def save_completed_weekly_review(self, *, key: WeeklyReviewCacheKey, advice: str, result_digest: str, now, agent_run_id=None) -> WeeklyReviewResult:
        """The unique cache key protects storage; callers use an existing terminal row when present."""
        existing = self.get_completed_weekly_review(key=key)
        if existing is not None:
            return existing
        result = WeeklyReviewResult(
            user_id=key.user_id, week_start=key.week_start, facts_digest=key.facts_digest, graph_version=key.graph_version,
            prompt_version=key.prompt_version, schema_version=key.schema_version, runtime_config_version=key.runtime_config_version,
            status="completed", advice=advice, abstention_code=None, result_digest=result_digest, agent_run_id=agent_run_id, created_at=now, updated_at=now,
        )
        self._session.add(result)
        self._session.flush()
        return result

    @staticmethod
    def _active_local_record_statement(*, user_id: uuid.UUID):
        return select(MealRecord).where(
            MealRecord.user_id == user_id,
            MealRecord.deleted_at.is_(None),
            MealRecord.consumed_local_date.is_not(None),
        )
