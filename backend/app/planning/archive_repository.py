"""Tenant-bound archive adapter; commits belong to the calling application service."""

import uuid
from datetime import date, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth.models import User
from app.agent.models import AgentThread, AgentEvent
from app.records.models import DashboardTimezonePreference
from app.planning.models import DietPlan, DietPlanVersion, ControlledRecipe, ManagedRecipeCandidate


class SqlAlchemyPlanArchiveRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def lock_owner(self, user_id: uuid.UUID) -> None:
        # A stable parent row also serializes the first plan, when no day row exists yet.
        self.session.execute(
            select(User.id).where(User.id == user_id).with_for_update()
        ).scalar_one()

    def time_zone(self, user_id: uuid.UUID) -> str | None:
        return self.session.scalar(
            select(DashboardTimezonePreference.time_zone).where(
                DashboardTimezonePreference.user_id == user_id
            )
        )

    def by_id(self, user_id: uuid.UUID, plan_id: uuid.UUID) -> DietPlan | None:
        return self.session.scalar(
            select(DietPlan)
            .where(DietPlan.user_id == user_id, DietPlan.id == plan_id)
            .execution_options(populate_existing=True)
        )

    def latest_deletion(self, user_id: uuid.UUID, day: date) -> datetime | None:
        return self.session.scalar(
            select(DietPlan.deleted_at)
            .where(
                DietPlan.user_id == user_id,
                DietPlan.plan_date == day,
                DietPlan.deleted_at.is_not(None),
            )
            .order_by(DietPlan.deleted_at.desc())
            .limit(1)
        )

    def by_date(self, user_id: uuid.UUID, day: date) -> DietPlan | None:
        return self.session.scalar(
            select(DietPlan)
            .where(
                DietPlan.user_id == user_id,
                DietPlan.plan_date == day,
                DietPlan.deleted_at.is_(None),
            )
            .execution_options(populate_existing=True)
        )

    def by_thread(self, user_id: uuid.UUID, thread_id: uuid.UUID) -> DietPlan | None:
        return self.session.scalar(
            select(DietPlan)
            .join(DietPlanVersion, DietPlanVersion.plan_id == DietPlan.id)
            .where(
                DietPlan.user_id == user_id,
                DietPlanVersion.user_id == user_id,
                DietPlanVersion.source_thread_id == thread_id,
            )
            .execution_options(populate_existing=True)
        )

    def by_run(self, user_id: uuid.UUID, run_id: uuid.UUID) -> DietPlanVersion | None:
        return self.session.scalar(
            select(DietPlanVersion).where(
                DietPlanVersion.user_id == user_id,
                DietPlanVersion.source_run_id == run_id,
            )
        )

    def version(
        self, user_id: uuid.UUID, plan_id: uuid.UUID, number: int
    ) -> DietPlanVersion | None:
        return self.session.scalar(
            select(DietPlanVersion).where(
                DietPlanVersion.user_id == user_id,
                DietPlanVersion.plan_id == plan_id,
                DietPlanVersion.version == number,
            )
        )

    def history(
        self, user_id: uuid.UUID, before: date | None, limit: int
    ) -> list[DietPlan]:
        query = select(DietPlan).where(
            DietPlan.user_id == user_id, DietPlan.deleted_at.is_(None)
        )
        if before is not None:
            query = query.where(DietPlan.plan_date < before)
        return list(
            self.session.scalars(query.order_by(DietPlan.plan_date.desc()).limit(limit))
        )

    def add_plan(self, plan: DietPlan) -> None:
        self.session.add(plan)
        self.session.flush()

    def add_version(self, version: DietPlanVersion) -> None:
        self.session.add(version)
        self.session.flush()

    def flush(self) -> None:
        self.session.flush()

    def erase_snapshots(self, user_id: uuid.UUID, plan_id: uuid.UUID) -> None:
        # Retain only idempotency tombstones so delayed completion cannot resurrect deleted food data.
        self.session.execute(
            update(DietPlanVersion)
            .where(
                DietPlanVersion.user_id == user_id, DietPlanVersion.plan_id == plan_id
            )
            .values(report=None, totals=None, provenance=None)
        )

    def resumable(self, user_id: uuid.UUID, thread_id: uuid.UUID) -> bool:
        thread = self.session.scalar(
            select(AgentThread).where(
                AgentThread.user_id == user_id,
                AgentThread.id == thread_id,
                AgentThread.deleted_at.is_(None),
            )
        )
        if thread is None:
            return False
        event = self.session.scalar(
            select(AgentEvent.id)
            .where(AgentEvent.user_id == user_id, AgentEvent.thread_id == thread_id)
            .limit(1)
        )
        return event is not None

    def recipe_versions(self, ids: tuple[uuid.UUID, ...]) -> list[dict[str, str]]:
        controlled = self.session.scalars(
            select(ControlledRecipe).where(ControlledRecipe.id.in_(ids))
        )
        versions = [
            {
                "recipe_id": str(row.id),
                "source_kind": "controlled_recipe",
                "recipe_version": row.recipe_version,
                "catalog_version": row.catalog_version,
                "audit_version": row.audit_version,
            }
            for row in controlled
        ]
        managed = self.session.scalars(
            select(ManagedRecipeCandidate).where(ManagedRecipeCandidate.id.in_(ids))
        )
        versions.extend(
            {
                "recipe_id": str(row.id),
                "source_kind": "managed_recipe_candidate",
                "recipe_version": f"managed-candidate.v{row.revision}",
                "catalog_version": row.nutrition_catalog_version,
                "audit_version": f"candidate-revision.v{row.revision}",
            }
            for row in managed
        )
        return versions
