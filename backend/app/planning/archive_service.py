"""Durable daily-plan use cases, independent of short-lived Agent storage."""

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.planning.archive_ports import PlanArchiveRepository
from app.planning.archive_schemas import (
    PlanArchiveWrite,
    PlanHistoryPage,
    PlanReport,
    SavedPlan,
    SavedPlanSummary,
    TodayPlan,
)
from app.planning.models import DietPlan, DietPlanVersion
from app.planning.schemas import PlanningNutritionValues


class PlanUnavailable(LookupError):
    """Missing, foreign and deleted resources intentionally share one result."""


class PlanArchiveConflict(ValueError):
    """A timezone or a current, non-deleted thread is required before generation."""


class PlanArchiveService:
    def __init__(
        self,
        *,
        repository: PlanArchiveRepository,
        now: Callable[[], datetime] | None = None,
        commit: Callable[[], None] | None = None,
        rollback: Callable[[], None] | None = None,
    ) -> None:
        self.repo = repository
        self.now = now or (lambda: datetime.now(UTC))
        self.commit = commit or (lambda: None)
        self.rollback = rollback or (lambda: None)

    def check_admission(self, *, user_id: uuid.UUID, thread_id: uuid.UUID) -> None:
        if self.repo.time_zone(user_id) is None:
            raise PlanArchiveConflict("请先确认计划与记录使用的统计时区。")
        bound = self.repo.by_thread(user_id, thread_id)
        if bound is not None:
            latest = self.repo.version(user_id, bound.id, bound.current_version)
            if (
                bound.deleted_at is not None
                or latest is None
                or latest.source_thread_id != thread_id
            ):
                raise PlanArchiveConflict(
                    "这份计划已删除或已被重新生成的计划替代，请打开当前计划。"
                )

    def record_completion(self, command: PlanArchiveWrite) -> None:
        """Flush only: archive and Agent completed state share the caller's transaction."""
        self.repo.lock_owner(command.user_id)
        self.check_admission(user_id=command.user_id, thread_id=command.thread_id)
        if self.repo.by_run(command.user_id, command.run_id) is not None:
            return
        time_zone = self.repo.time_zone(command.user_id)
        assert time_zone is not None
        plan = self.repo.by_thread(command.user_id, command.thread_id)
        if plan is None:
            day = command.started_at.astimezone(ZoneInfo(time_zone)).date()
            deleted_at = self.repo.latest_deletion(command.user_id, day)
            if deleted_at is not None and command.started_at <= deleted_at:
                raise PlanArchiveConflict("生成期间这天的计划已被删除，请重新生成。")
            plan = self.repo.by_date(command.user_id, day)
        now = self.now()
        if plan is None:
            plan = DietPlan(
                id=uuid.uuid4(),
                user_id=command.user_id,
                plan_date=command.started_at.astimezone(ZoneInfo(time_zone)).date(),
                time_zone=time_zone,
                current_version=1,
                created_at=now,
                updated_at=now,
            )
            self.repo.add_plan(plan)
        else:
            plan.current_version += 1
            plan.updated_at = now
        totals = PlanningNutritionValues(
            **{
                metric: sum(
                    (getattr(meal.nutrients, metric) for meal in command.report.meals),
                    Decimal(0),
                )
                for metric in PlanningNutritionValues.model_fields
            }
        )
        provenance = {
            "schema_version": "diet-plan-snapshot.v2" if command.component_recipes else "diet-plan-snapshot.v1",
            "validation": "completed_validated",
            "target_version": command.target_version,
            "formula_version": command.formula_version,
            "graph_version": command.graph_version,
            "tool_version": command.tool_version,
            "recipes": [*self.repo.recipe_versions(tuple(
                identity for identity in command.recipe_ids
                if identity not in {item.recipe_id for item in command.component_recipes}
            )), *(item.model_dump(mode="json") for item in command.component_recipes)],
        }
        self.repo.add_version(
            DietPlanVersion(
                id=uuid.uuid4(),
                user_id=command.user_id,
                plan_id=plan.id,
                version=plan.current_version,
                source_run_id=command.run_id,
                source_thread_id=command.thread_id,
                report=command.report.model_dump(mode="json", exclude_none=True),
                totals=totals.model_dump(mode="json"),
                provenance=provenance,
                created_at=now,
            )
        )
        self.repo.flush()

    def today(self, user_id: uuid.UUID) -> TodayPlan:
        zone = self.repo.time_zone(user_id)
        if zone is None:
            return TodayPlan(time_zone=None, today=None, plan=None)
        day = self.now().astimezone(ZoneInfo(zone)).date()
        row = self.repo.by_date(user_id, day)
        return TodayPlan(
            time_zone=zone,
            today=day,
            plan=self.detail(user_id, row.id) if row else None,
        )

    def history(
        self, user_id: uuid.UUID, before: date | None, limit: int
    ) -> PlanHistoryPage:
        rows = self.repo.history(user_id, before, limit + 1)
        return PlanHistoryPage(
            items=tuple(SavedPlanSummary.model_validate(row) for row in rows[:limit]),
            next_before=rows[limit - 1].plan_date if len(rows) > limit else None,
        )

    def detail(
        self, user_id: uuid.UUID, plan_id: uuid.UUID, version: int | None = None
    ) -> SavedPlan:
        row = self.repo.by_id(user_id, plan_id)
        if row is None or row.deleted_at is not None:
            raise PlanUnavailable()
        saved = self.repo.version(user_id, row.id, version or row.current_version)
        if saved is None or saved.report is None or saved.totals is None:
            raise PlanUnavailable()
        current_day = self.now().astimezone(ZoneInfo(row.time_zone)).date()
        can_adjust = (
            saved.version == row.current_version
            and row.plan_date == current_day
            and self.repo.resumable(user_id, saved.source_thread_id)
        )
        return SavedPlan(
            **SavedPlanSummary.model_validate(row).model_dump(),
            version=saved.version,
            saved_at=saved.created_at,
            report=PlanReport.model_validate(saved.report),
            totals=PlanningNutritionValues.model_validate(saved.totals),
            adjustment_thread_id=saved.source_thread_id if can_adjust else None,
        )

    def delete(self, user_id: uuid.UUID, plan_id: uuid.UUID) -> None:
        try:
            self.repo.lock_owner(user_id)
            row = self.repo.by_id(user_id, plan_id)
            if row is None or row.deleted_at is not None:
                raise PlanUnavailable()
            row.deleted_at = self.now()
            self.repo.erase_snapshots(user_id, plan_id)
            self.repo.flush()
            self.commit()
        except Exception:
            self.rollback()
            raise
