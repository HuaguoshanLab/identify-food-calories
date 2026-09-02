"""RED contracts for the revocable, authoritative completed-plan projection."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.dashboard.ports import PlanningTargetEligibility
from app.planning.models import PlanningCompletionProjection, PlanningProfile
from app.planning.ports import PlanningCompletionProjectionRepository
from app.planning.schemas import (
    ActivityLevel,
    DailyTarget,
    FormulaVariant,
    PlanningGoal,
    PlanningProfilePatch,
    TargetRange,
)
from app.planning.service import PlanningCompletionProjectionService, PlanningProfileService


NOW = datetime(2026, 9, 2, tzinfo=UTC)


class FakeProjectionRepository:
    def __init__(self, profile: PlanningProfile) -> None:
        self.profile = profile
        self.projections: list[PlanningCompletionProjection] = []

    def get_profile_for_user(self, *, user_id: uuid.UUID, for_update: bool = False) -> PlanningProfile | None:
        return self.profile if self.profile.user_id == user_id and self.profile.deleted_at is None else None

    def add_completion_projection(self, projection: PlanningCompletionProjection) -> PlanningCompletionProjection:
        self.projections.append(projection)
        return projection

    def get_completion_projection_for_user(
        self, *, user_id: uuid.UUID, for_update: bool = False
    ) -> PlanningCompletionProjection | None:
        return next(
            (item for item in self.projections if item.user_id == user_id and item.revoked_at is None),
            None,
        )

    def revoke_completion_projection_for_user(
        self, *, user_id: uuid.UUID, reason: str, revoked_at: datetime
    ) -> bool:
        projection = self.get_completion_projection_for_user(user_id=user_id, for_update=True)
        if projection is None:
            return False
        projection.revoked_at = revoked_at
        projection.revocation_reason = reason
        return True

    def get_dashboard_target_eligibility(self, *, user_id: uuid.UUID) -> PlanningTargetEligibility:
        projection = self.get_completion_projection_for_user(user_id=user_id)
        return PlanningTargetEligibility.unavailable() if projection is None else PlanningTargetEligibility.from_projection(projection)


def _profile(*, user_id: uuid.UUID) -> PlanningProfile:
    return PlanningProfile(
        id=uuid.uuid4(), user_id=user_id, height_cm=Decimal("170"), weight_kg=Decimal("65"),
        age_years=30, formula_variant=FormulaVariant.MIFFLIN_ST_JEOR_FEMALE.value,
        activity_level=ActivityLevel.MODERATE.value, goal=PlanningGoal.LOSS.value,
        goal_speed="gradual_loss", target_policy_version="target-policy.v1",
        formula_version="mifflin-st-jeor.v1", revision=3, created_at=NOW, updated_at=NOW, deleted_at=None,
    )


def _target() -> DailyTarget:
    return DailyTarget(
        energy_kcal=TargetRange(lower=Decimal("1800"), upper=Decimal("2000")),
        carbohydrate_g=TargetRange(lower=Decimal("200"), upper=Decimal("300")),
        protein_g=TargetRange(lower=Decimal("80"), upper=Decimal("120")),
        fat_g=TargetRange(lower=Decimal("40"), upper=Decimal("70")),
    )


def test_validated_completion_creates_owner_bound_projection_and_commits_once() -> None:
    user_id = uuid.uuid4()
    repository = FakeProjectionRepository(_profile(user_id=user_id))
    commits: list[str] = []

    projection = PlanningCompletionProjectionService(
        repository=repository, now=lambda: NOW, commit=lambda: commits.append("commit")
    ).record_validated_completion(
        user_id=user_id, run_id=uuid.uuid4(), thread_id=uuid.uuid4(), target=_target()
    )

    assert commits == ["commit"]
    assert projection.user_id == user_id
    assert projection.completed_at == NOW
    assert projection.profile_revision == 3
    assert projection.target_version == "target-policy.v1"
    assert projection.revoked_at is None
    eligibility = repository.get_dashboard_target_eligibility(user_id=user_id)
    assert eligibility.eligible is True
    assert eligibility.target is not None and eligibility.target.energy_kcal.lower == Decimal("1800")


def test_projection_write_failure_rolls_back_without_granting_eligibility() -> None:
    user_id = uuid.uuid4()
    repository = FakeProjectionRepository(_profile(user_id=user_id))
    rollbacks: list[str] = []
    service = PlanningCompletionProjectionService(
        repository=repository,
        now=lambda: NOW,
        commit=lambda: (_ for _ in ()).throw(RuntimeError("database unavailable")),
        rollback=lambda: rollbacks.append("rollback"),
    )

    with pytest.raises(RuntimeError, match="database unavailable"):
        service.record_validated_completion(user_id=user_id, run_id=uuid.uuid4(), thread_id=uuid.uuid4(), target=_target())
    assert rollbacks == ["rollback"]


def test_profile_change_and_delete_revoke_only_the_owners_projection() -> None:
    owner = uuid.uuid4()
    other = uuid.uuid4()
    repository = FakeProjectionRepository(_profile(user_id=owner))
    completion = PlanningCompletionProjectionService(repository=repository, now=lambda: NOW)
    completion.record_validated_completion(user_id=owner, run_id=uuid.uuid4(), thread_id=uuid.uuid4(), target=_target())

    profile_service = PlanningProfileService(repository=repository, completion_repository=repository, now=lambda: NOW)
    profile_service.update_profile(user_id=owner, payload=PlanningProfilePatch(goal=PlanningGoal.GAIN, goal_speed="gradual_gain"))

    eligibility = repository.get_dashboard_target_eligibility(user_id=owner)
    assert eligibility.eligible is False and eligibility.target is None
    assert repository.projections[0].revocation_reason == "profile_revision_changed"
    assert repository.get_dashboard_target_eligibility(user_id=other).eligible is False

