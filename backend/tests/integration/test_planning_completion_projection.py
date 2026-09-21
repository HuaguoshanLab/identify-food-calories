"""RED PostgreSQL evidence for completed-plan projection constraints and revocation."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.agent.models import AgentRun, AgentThread
from app.auth.models import User, UserRole
from app.planning.models import PlanningCompletionProjection, PlanningProfile
from app.planning.repository import SqlAlchemyPlanningProfileRepository
from app.planning.schemas import DailyTarget, TargetRange
from app.planning.service import PlanningCompletionProjectionService


pytestmark = pytest.mark.skipif(
    os.environ.get("APP_ENV") != "test",
    reason="requires the guarded PostgreSQL test environment",
)


def test_completion_projection_rejects_orphans_and_exposes_no_cross_user_target(db_session) -> None:
    now = datetime(2026, 9, 2, tzinfo=UTC)
    user = User(
        id=uuid.uuid4(), email=f"projection-{uuid.uuid4().hex}@example.test", password_hash="digest",
        role=UserRole.USER.value, is_active=True, email_verified_at=now, created_at=now, updated_at=now,
    )
    db_session.add(user)
    db_session.commit()
    profile = PlanningProfile(
        id=uuid.uuid4(), user_id=user.id, height_cm=Decimal("170"), weight_kg=Decimal("65"), age_years=30,
        formula_variant="mifflin_st_jeor_female", activity_level="moderate", goal="loss", goal_speed="gradual_loss",
        target_policy_version="target-policy.v1", formula_version="mifflin-st-jeor.v1", revision=1,
        created_at=now, updated_at=now, deleted_at=None,
    )
    thread = AgentThread(id=uuid.uuid4(), user_id=user.id, status="completed", revision=1, created_at=now, last_activity_at=now, deleted_at=None)
    run = AgentRun(
        id=uuid.uuid4(), user_id=user.id, thread_id=thread.id, command_key="projection-run-0001", command_hash="a" * 64,
        status="completed", graph_version="diet.v1", prompt_version="prompt.v1", tool_version="tools.v1",
        model_provider=None, model_version=None, graph_steps=1, model_calls=0, tool_calls=1, elapsed_ms=1,
        estimated_cost_usd=Decimal("0"), failure_code=None, created_at=now, updated_at=now, finished_at=now,
    )
    db_session.add_all([profile, thread])
    db_session.commit()
    db_session.add(run)
    db_session.commit()

    repository = SqlAlchemyPlanningProfileRepository(db_session)
    PlanningCompletionProjectionService(repository=repository, now=lambda: now, commit=db_session.commit, rollback=db_session.rollback).record_validated_completion(
        user_id=user.id,
        run_id=run.id,
        thread_id=thread.id,
        source_profile=repository.get_planning_profile(user_id=user.id),
        target=DailyTarget(
            energy_kcal=TargetRange(lower=Decimal("1800"), upper=Decimal("2000")),
            carbohydrate_g=TargetRange(lower=Decimal("200"), upper=Decimal("300")),
            protein_g=TargetRange(lower=Decimal("80"), upper=Decimal("120")),
            fat_g=TargetRange(lower=Decimal("40"), upper=Decimal("70")),
        ),
    )
    assert repository.get_dashboard_target_eligibility(user_id=user.id).eligible is True

    projection = PlanningCompletionProjection(
        id=uuid.uuid4(), user_id=user.id, profile_id=profile.id, completed_run_id=uuid.uuid4(), completed_thread_id=thread.id,
        profile_revision=1, target_version="target-policy.v1", energy_kcal_lower=Decimal("1800"),
        energy_kcal_upper=Decimal("2000"), carbohydrate_g_lower=Decimal("200"), carbohydrate_g_upper=Decimal("300"),
        protein_g_lower=Decimal("80"), protein_g_upper=Decimal("120"), fat_g_lower=Decimal("40"),
        fat_g_upper=Decimal("70"), completed_at=now, revoked_at=None, revocation_reason=None,
    )
    db_session.add(projection)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_completion_projection_rejects_a_run_or_thread_from_another_user(db_session) -> None:
    now = datetime(2026, 9, 2, tzinfo=UTC)
    owner = User(
        id=uuid.uuid4(), email=f"projection-owner-{uuid.uuid4().hex}@example.test", password_hash="digest",
        role=UserRole.USER.value, is_active=True, email_verified_at=now, created_at=now, updated_at=now,
    )
    other = User(
        id=uuid.uuid4(), email=f"projection-other-{uuid.uuid4().hex}@example.test", password_hash="digest",
        role=UserRole.USER.value, is_active=True, email_verified_at=now, created_at=now, updated_at=now,
    )
    db_session.add_all([owner, other])
    db_session.commit()
    profile = PlanningProfile(
        id=uuid.uuid4(), user_id=owner.id, height_cm=Decimal("170"), weight_kg=Decimal("65"), age_years=30,
        formula_variant="mifflin_st_jeor_female", activity_level="moderate", goal="loss", goal_speed="gradual_loss",
        target_policy_version="target-policy.v1", formula_version="mifflin-st-jeor.v1", revision=1,
        created_at=now, updated_at=now, deleted_at=None,
    )
    other_thread = AgentThread(id=uuid.uuid4(), user_id=other.id, status="completed", revision=1, created_at=now, last_activity_at=now, deleted_at=None)
    db_session.add_all([profile, other_thread])
    db_session.commit()
    other_run = AgentRun(
        id=uuid.uuid4(), user_id=other.id, thread_id=other_thread.id, command_key="projection-other-run-0001", command_hash="b" * 64,
        status="completed", graph_version="diet.v1", prompt_version="prompt.v1", tool_version="tools.v1",
        model_provider=None, model_version=None, graph_steps=1, model_calls=0, tool_calls=1, elapsed_ms=1,
        estimated_cost_usd=Decimal("0"), failure_code=None, created_at=now, updated_at=now, finished_at=now,
    )
    db_session.add(other_run)
    db_session.commit()
    db_session.add(
        PlanningCompletionProjection(
            id=uuid.uuid4(), user_id=owner.id, profile_id=profile.id, completed_thread_id=other_thread.id,
            completed_run_id=other_run.id, profile_revision=1, target_version="target-policy.v1",
            energy_kcal_lower=Decimal("1800"), energy_kcal_upper=Decimal("2000"),
            carbohydrate_g_lower=Decimal("200"), carbohydrate_g_upper=Decimal("300"),
            protein_g_lower=Decimal("80"), protein_g_upper=Decimal("120"), fat_g_lower=Decimal("40"),
            fat_g_upper=Decimal("70"), completed_at=now, revoked_at=None, revocation_reason=None,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
