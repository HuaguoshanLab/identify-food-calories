"""Fake-port contracts for explicit minimal profile persistence semantics."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.planning.models import PlanningProfile
from app.planning.schemas import ActivityLevel, FormulaVariant, PlanningGoal, PlanningProfilePatch, PlanningProfileWrite
from app.planning.service import PlanningProfileService, PlanningProfileUnavailable


class FakePlanningProfileRepository:
    def __init__(self) -> None:
        self._profiles: list[PlanningProfile] = []

    def get_profile_for_user(self, *, user_id: uuid.UUID, for_update: bool = False) -> PlanningProfile | None:
        return next((profile for profile in self._profiles if profile.user_id == user_id and profile.deleted_at is None), None)

    def add_profile(self, profile: PlanningProfile) -> PlanningProfile:
        self._profiles.append(profile)
        return profile


def _payload() -> PlanningProfileWrite:
    return PlanningProfileWrite(
        height_cm=Decimal("170"), weight_kg=Decimal("65"), age_years=30,
        formula_variant=FormulaVariant.MIFFLIN_ST_JEOR_FEMALE, activity_level=ActivityLevel.MODERATE,
        goal=PlanningGoal.LOSS, goal_speed="gradual_loss",
    )


def test_profile_service_saves_updates_and_hides_deleted_profiles_from_every_user() -> None:
    repository = FakePlanningProfileRepository()
    commits: list[str] = []
    now = datetime(2026, 9, 1, tzinfo=UTC)
    service = PlanningProfileService(repository=repository, now=lambda: now, commit=lambda: commits.append("commit"))
    owner = uuid.uuid4()

    saved = service.replace_profile(user_id=owner, payload=_payload())
    assert saved.target_policy_version == "target-policy.v1" and commits == ["commit"]
    updated = service.update_profile(
        user_id=owner, payload=PlanningProfilePatch(goal=PlanningGoal.GAIN, goal_speed="gradual_gain")
    )
    assert updated.goal == "gain" and updated.goal_speed == "gradual_gain"
    service.delete_profile(user_id=owner)
    assert saved.deleted_at == now
    with pytest.raises(PlanningProfileUnavailable):
        service.get_profile(user_id=owner)
    with pytest.raises(PlanningProfileUnavailable):
        service.get_profile(user_id=uuid.uuid4())


def test_profile_service_rolls_back_failed_create() -> None:
    repository = FakePlanningProfileRepository()
    rollbacks: list[str] = []
    service = PlanningProfileService(
        repository=repository,
        commit=lambda: (_ for _ in ()).throw(RuntimeError("database unavailable")),
        rollback=lambda: rollbacks.append("rollback"),
    )

    with pytest.raises(RuntimeError, match="database unavailable"):
        service.replace_profile(user_id=uuid.uuid4(), payload=_payload())
    assert rollbacks == ["rollback"]
