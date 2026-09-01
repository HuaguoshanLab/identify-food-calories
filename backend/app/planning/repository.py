"""Tenant-filtered SQLAlchemy adapter for the minimal planning profile authority."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.planning.models import PlanningProfile
from app.planning.schemas import ActivityLevel, FormulaVariant, PlanningGoal, PlanningProfileInput


class SqlAlchemyPlanningProfileRepository:
    """Ownership is proved in SQL so profile IDs never become an existence oracle."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_profile_for_user(self, *, user_id: uuid.UUID, for_update: bool = False) -> PlanningProfile | None:
        statement = self._profile_statement(user_id=user_id)
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def get_planning_profile(self, *, user_id: uuid.UUID) -> PlanningProfileInput | None:
        profile = self.get_profile_for_user(user_id=user_id)
        if profile is None:
            return None
        return PlanningProfileInput(
            height_cm=profile.height_cm, weight_kg=profile.weight_kg, age_years=profile.age_years,
            formula_variant=FormulaVariant(profile.formula_variant),
            activity_level=ActivityLevel(profile.activity_level),
            goal=PlanningGoal(profile.goal), goal_speed=profile.goal_speed,
        )

    def add_profile(self, profile: PlanningProfile) -> PlanningProfile:
        self._session.add(profile)
        self._session.flush()
        return profile

    @staticmethod
    def _profile_statement(*, user_id: uuid.UUID):
        return select(PlanningProfile).where(
            PlanningProfile.user_id == user_id, PlanningProfile.deleted_at.is_(None)
        )
