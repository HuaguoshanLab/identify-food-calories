"""Public PostgreSQL contracts for the tenant-bound diet-planning command."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.auth.api import get_authentication_service
from app.auth.models import AuthSession, User, UserRole
from app.auth.repository import SqlAlchemyAuthRepository
from app.auth.security import issue_access_token
from app.auth.service import AuthenticationService
from app.core.config import Settings, validate_test_database_configuration
from app.main import create_app
from app.records.models import PreferenceMemoryLedger, DashboardTimezonePreference
from app.planning.models import PlanningCompletionProjection, PlanningProfile
from app.planning.schemas import HEALTH_REFUSAL_MESSAGE


BACKEND_ROOT = Path(__file__).resolve().parents[2]
SECRET = "diet-planning-agent-api-secret-with-at-least-forty-eight-bytes"
PLANNING_PATH = "/api/v1/agent/threads/diet-planning"
SYNTHETIC_ORDINARY_ADULT_PROFILE = {
    "height_cm": "149",
    "weight_kg": "71",
    "age_years": 61,
    "activity_level": "sedentary",
    "goal": "maintain",
    "goal_speed": "maintain",
}


def _settings() -> Settings:
    return Settings(
        app_env="test",
        database_url="postgresql+psycopg://postgres:postgres@localhost:5432/food_agent_dev",
        test_database_url="postgresql+psycopg://postgres:postgres@localhost:55432/food_agent_test",
        secret_key=SECRET,
        _env_file=None,
    )


def _test_env(settings: Settings) -> dict[str, str]:
    return os.environ | {
        "APP_ENV": "test",
        "DATABASE_URL": settings.database_url,
        "TEST_DATABASE_URL": settings.test_database_url or "",
    }


def _create_user(session: Session, *, label: str) -> tuple[User, str]:
    from app.admin.repository import SqlAlchemyAdminRepository
    from app.admin.service import AdminService
    from app.admin.schemas import RuntimeConfigCommand
    now = datetime.now(UTC)
    if SqlAlchemyAdminRepository(session).get_active_runtime_config() is None:
        actor = User(id=uuid.uuid4(), email=f"planning-admin-{uuid.uuid4().hex}@example.test", password_hash="digest", role=UserRole.ADMIN.value, is_active=True, email_verified_at=now, created_at=now, updated_at=now)
        session.add(actor)
        session.flush()
        AdminService(repository=SqlAlchemyAdminRepository(session), now=lambda: now, commit=session.commit, rollback=session.rollback).configure_runtime(actor_user_id=actor.id, command=RuntimeConfigCommand(provider="deepseek", model_alias="deepseek-v4-flash", enabled=True, single_call_cap_usd="0.03", period_cap_usd="3", input_usd_per_m="0.2", output_usd_per_m="0.8", reason="planning integration fake provider", confirm=True), command_key="planning-test-runtime")
    user = User(
        id=uuid.uuid4(),
        email=f"diet-planning-{label}-{uuid.uuid4().hex}@example.test",
        password_hash="argon2id-digest",
        role=UserRole.USER.value,
        is_active=True,
        email_verified_at=now,
        created_at=now,
        updated_at=now,
    )
    auth_session = AuthSession(
        id=uuid.uuid4(), user_id=user.id, family_id=uuid.uuid4(), created_at=now,
        last_seen_at=now, expires_at=now + timedelta(days=30),
    )
    session.add_all([user, auth_session])
    session.commit()
    session.add(DashboardTimezonePreference(user_id=user.id, time_zone="Asia/Shanghai", confirmed_at=now))
    session.commit()
    token, _ = issue_access_token(
        secret_key=SECRET, user_id=user.id, role=UserRole.USER.value,
        issuer="food-agent-api", audience="food-agent-h5", issued_at=now, session_id=auth_session.id,
    )
    return user, token


def _command(
    *, confirmed: bool = True, save_profile: bool = True, profile_overrides: dict[str, object] | None = None
) -> dict[str, object]:
    profile: dict[str, object] = {
        "height_cm": "170",
        "weight_kg": "65",
        "age_years": 30,
        "formula_variant": "mifflin_st_jeor_female",
        "activity_level": "moderate",
        "goal": "loss",
        "goal_speed": "gradual_loss",
    }
    profile.update(profile_overrides or {})
    return {
        "profile": profile,
        "preferences": {
            "confirmed": confirmed,
            "exclusions": ["花生"],
            "taste_preferences": ["清淡"],
        },
        "save_profile": save_profile,
    }


def test_health_scope_remains_fail_closed_through_public_planning_api() -> None:
    settings = _settings()
    test_url = validate_test_database_configuration(settings)
    subprocess.run(
        [sys.executable, "scripts/run_initialized_app.py", "--prepare-only"],
        cwd=BACKEND_ROOT,
        env=_test_env(settings),
        check=True,
    )
    engine = create_engine(test_url)
    try:
        with Session(engine) as session:
            user, token = _create_user(session, label="health-scope")
            authentication = AuthenticationService(
                repository=SqlAlchemyAuthRepository(session), secret_key=SECRET,
                issuer="food-agent-api", audience="food-agent-h5",
                commit=session.commit, rollback=session.rollback,
            )
            app = create_app(settings)
            app.dependency_overrides[get_authentication_service] = lambda: authentication
            with TestClient(app) as client:
                response = client.post(
                    PLANNING_PATH,
                    json=_command(profile_overrides={"age_years": 18}),
                    headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "diet-plan-health-scope-0001"},
                )

            assert response.status_code == 201, response.text
            snapshot = response.json()
            assert snapshot["status"] == "retryable"
            assert snapshot["report"] == {"stage": "needs_input", "message": HEALTH_REFUSAL_MESSAGE}
            assert session.query(PlanningProfile).filter_by(user_id=user.id, deleted_at=None).count() == 0
    finally:
        engine.dispose()


def test_public_api_composes_v2_seed_above_floor_for_a_synthetic_ordinary_adult() -> None:
    settings = _settings()
    test_url = validate_test_database_configuration(settings)
    subprocess.run(
        [sys.executable, "scripts/run_initialized_app.py", "--prepare-only"],
        cwd=BACKEND_ROOT,
        env=_test_env(settings),
        check=True,
    )
    engine = create_engine(test_url)
    try:
        with Session(engine) as session:
            user, token = _create_user(session, label="v2-seed-adult")
            authentication = AuthenticationService(
                repository=SqlAlchemyAuthRepository(session), secret_key=SECRET,
                issuer="food-agent-api", audience="food-agent-h5",
                commit=session.commit, rollback=session.rollback,
            )
            app = create_app(settings)
            app.dependency_overrides[get_authentication_service] = lambda: authentication
            with TestClient(app) as client:
                response = client.post(
                    PLANNING_PATH,
                    json=_command(profile_overrides=SYNTHETIC_ORDINARY_ADULT_PROFILE),
                    headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "diet-plan-v2-seed-adult-0001"},
                )

            assert response.status_code == 201, response.text
            report = response.json()["report"]
            assert response.json()["status"] == "completed"
            total_energy = sum(
                (Decimal(meal["nutrients"]["energy_kcal"]) for meal in report["meals"]),
                Decimal("0"),
            )
            assert total_energy >= Decimal("1200")
            assert Decimal(report["target"]["energy_kcal"]["lower"]) <= total_energy
            assert total_energy <= Decimal(report["target"]["energy_kcal"]["upper"])
    finally:
        engine.dispose()


def test_diet_planning_command_is_owner_scoped_idempotent_and_streams_only_safe_business_events() -> None:
    settings = _settings()
    test_url = validate_test_database_configuration(settings)
    subprocess.run(
        [sys.executable, "scripts/run_initialized_app.py", "--prepare-only"],
        cwd=BACKEND_ROOT,
        env=_test_env(settings),
        check=True,
    )
    engine = create_engine(test_url)
    try:
        with Session(engine) as session:
            owner, owner_token = _create_user(session, label="owner")
            _other, other_token = _create_user(session, label="other")
            authentication = AuthenticationService(
                repository=SqlAlchemyAuthRepository(session), secret_key=SECRET,
                issuer="food-agent-api", audience="food-agent-h5",
                commit=session.commit, rollback=session.rollback,
            )
            app = create_app(settings)
            app.dependency_overrides[get_authentication_service] = lambda: authentication
            headers = {
                "Authorization": f"Bearer {owner_token}",
                "Idempotency-Key": "diet-planning-command-0001",
            }
            with TestClient(app) as client:
                created = client.post(PLANNING_PATH, json=_command(), headers=headers)
                assert created.status_code == 201, created.text
                snapshot = created.json()
                assert snapshot["status"] == "completed"
                assert [meal["slot"] for meal in snapshot["report"]["meals"]] == [
                    "breakfast", "lunch", "dinner"
                ]
                thread_id = snapshot["thread_id"]

                repeated = client.post(PLANNING_PATH, json=_command(), headers=headers)
                assert repeated.status_code == 201, repeated.text
                assert repeated.json()["thread_id"] == thread_id
                assert client.get(
                    f"/api/v1/agent/threads/{thread_id}",
                    headers={"Authorization": f"Bearer {other_token}"},
                ).status_code == 404

                stream = client.get(
                    f"/api/v1/agent/threads/{thread_id}/events",
                    headers={"Authorization": f"Bearer {owner_token}"},
                )
                assert stream.status_code == 200
                for forbidden in ("provider", "prompt", "candidate", "tool_output", "cost", "recipe_id"):
                    assert forbidden not in stream.text
                assert '"schema_version":"safe-stream-stage.v1"' in stream.text
                assert '"stage":"completed"' in stream.text

                blocked_command = _command(save_profile=False)
                blocked_command["preferences"]["exclusions"] = ["原味酸奶燕麦杯"]
                blocked = client.post(PLANNING_PATH, json=blocked_command, headers={
                    "Authorization": f"Bearer {owner_token}", "Idempotency-Key": "planning-no-breakfast-0001",
                })
                assert blocked.status_code == 201
                assert blocked.json()["status"] == "terminal"
                failure = blocked.json()["report"]
                assert set(failure) == {"stage", "message"}
                assert "早餐没有可用候选" in failure["message"]
                assert "三次" not in failure["message"]
                failure_id = blocked.json()["thread_id"]
                reread = client.get(f"/api/v1/agent/threads/{failure_id}", headers={"Authorization": f"Bearer {owner_token}"})
                assert reread.json()["report"] == failure
                assert "metrics" not in reread.text and "原味酸奶燕麦杯" not in reread.text

            assert session.query(PlanningProfile).filter_by(user_id=owner.id, deleted_at=None).count() == 1
            projection = session.query(PlanningCompletionProjection).filter_by(user_id=owner.id, revoked_at=None).one()
            assert projection.completed_thread_id == uuid.UUID(thread_id)
            assert projection.target_version == "target-policy.v1"
    finally:
        engine.dispose()


def test_unconfirmed_or_unsaved_diet_planning_commands_never_write_a_profile() -> None:
    settings = _settings()
    test_url = validate_test_database_configuration(settings)
    subprocess.run(
        [sys.executable, "scripts/run_initialized_app.py", "--prepare-only"],
        cwd=BACKEND_ROOT,
        env=_test_env(settings),
        check=True,
    )
    engine = create_engine(test_url)
    try:
        with Session(engine) as session:
            user, token = _create_user(session, label="not-saved")
            authentication = AuthenticationService(
                repository=SqlAlchemyAuthRepository(session), secret_key=SECRET,
                issuer="food-agent-api", audience="food-agent-h5",
                commit=session.commit, rollback=session.rollback,
            )
            app = create_app(settings)
            app.dependency_overrides[get_authentication_service] = lambda: authentication
            with TestClient(app) as client:
                unconfirmed = client.post(
                    PLANNING_PATH,
                    json=_command(confirmed=False, save_profile=True),
                    headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "diet-plan-unconfirmed-0001"},
                )
                assert unconfirmed.status_code == 201, unconfirmed.text
                assert unconfirmed.json()["status"] == "waiting"
                unsaved = client.post(
                    PLANNING_PATH,
                    json=_command(save_profile=False),
                    headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "diet-plan-unsaved-000001"},
                )
                assert unsaved.status_code == 201, unsaved.text
                assert unsaved.json()["status"] == "completed"
            assert session.query(PlanningProfile).filter_by(user_id=user.id, deleted_at=None).count() == 0
    finally:
        engine.dispose()


def test_same_planning_thread_adjusts_only_the_named_slot_and_replays_safe_events() -> None:
    settings = _settings()
    test_url = validate_test_database_configuration(settings)
    subprocess.run(
        [sys.executable, "scripts/run_initialized_app.py", "--prepare-only"],
        cwd=BACKEND_ROOT,
        env=_test_env(settings),
        check=True,
    )
    engine = create_engine(test_url)
    try:
        with Session(engine) as session:
            user, token = _create_user(session, label="adjustment")
            authentication = AuthenticationService(
                repository=SqlAlchemyAuthRepository(session), secret_key=SECRET,
                issuer="food-agent-api", audience="food-agent-h5",
                commit=session.commit, rollback=session.rollback,
            )
            app = create_app(settings)
            app.dependency_overrides[get_authentication_service] = lambda: authentication
            headers = {
                "Authorization": f"Bearer {token}",
                "Idempotency-Key": "diet-plan-adjustment-0001",
            }
            with TestClient(app) as client:
                created = client.post(PLANNING_PATH, json=_command(), headers=headers)
                assert created.status_code == 201, created.text
                before = created.json()
                before_names = [meal["display_name"] for meal in before["report"]["meals"]]

                adjusted = client.post(
                    f"/api/v1/agent/threads/{before['thread_id']}/input",
                    json={"kind": "description", "text": "午餐换清淡一些，不吃香菜"},
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert adjusted.status_code == 202, adjusted.text
                snapshot = client.get(
                    f"/api/v1/agent/threads/{before['thread_id']}",
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert snapshot.status_code == 200, snapshot.text
                report = snapshot.json()["report"]
                after_names = [meal["display_name"] for meal in report["meals"]]
                assert after_names[0] == before_names[0]
                assert after_names[2] == before_names[2]
                assert report["adjustment"]["changed_slots"] == ["lunch"]
                assert report["adjustment"]["range_status"]

                stream = client.get(
                    f"/api/v1/agent/threads/{before['thread_id']}/events",
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert stream.status_code == 200
                for forbidden in ("午餐换清淡", "香菜", "ledger", "provider", "tool_output", "reasoning"):
                    assert forbidden not in stream.text

            captured = session.query(PreferenceMemoryLedger).filter_by(
                user_id=user.id, category="avoidance", deleted_at=None
            ).all()
            # A meal-scoped adjustment applies now; it must not become a future
            # long-term exclusion after the temporary-preference separation.
            assert captured == []
    finally:
        engine.dispose()


def test_saved_plan_api_preserves_versions_and_survives_runtime_cleanup(monkeypatch) -> None:
    from sqlalchemy import delete, select
    from app.core.database import get_session
    from app.agent.models import AgentEvent
    from app.planning.models import DietPlanVersion

    settings = _settings()
    test_url = validate_test_database_configuration(settings)
    subprocess.run([sys.executable, "scripts/run_initialized_app.py", "--prepare-only"], cwd=BACKEND_ROOT, env=_test_env(settings), check=True)
    engine = create_engine(test_url)
    try:
        with Session(engine) as session:
            owner, token = _create_user(session, label="archive")
            _, other_token = _create_user(session, label="archive-other")
            authentication = AuthenticationService(repository=SqlAlchemyAuthRepository(session), secret_key=SECRET, issuer="food-agent-api", audience="food-agent-h5", commit=session.commit, rollback=session.rollback)
            app = create_app(settings)
            app.dependency_overrides[get_authentication_service] = lambda: authentication
            app.dependency_overrides[get_session] = lambda: session
            headers = {"Authorization": f"Bearer {token}"}
            other_headers = {"Authorization": f"Bearer {other_token}"}
            path = "/api/v1/planning/plans"
            with TestClient(app) as client:
                assert client.get(path).status_code == 401
                assert client.get(path + "/today", headers=headers).json()["plan"] is None
                command = _command(save_profile=False)
                first = client.post(PLANNING_PATH, json=command, headers=headers | {"Idempotency-Key": "archive-first"})
                assert first.status_code == 201 and first.json()["status"] == "completed", first.text
                today = client.get(path + "/today", headers=headers)
                assert today.status_code == 200, today.text
                plan = today.json()["plan"]
                assert plan["current_version"] == 1 and plan["report"]["meals"]
                plan_id = plan["id"]
                assert client.get(path + f"/{plan_id}", headers=other_headers).status_code == 404
                assert client.delete(path + f"/{plan_id}", headers=other_headers).status_code == 404
                assert session.query(PlanningProfile).filter_by(user_id=owner.id).count() == 0
                assert client.post(PLANNING_PATH, json=command, headers=headers | {"Idempotency-Key": "archive-first"}).status_code == 201
                assert client.get(path + f"/{plan_id}", headers=headers).json()["current_version"] == 1
                second = client.post(PLANNING_PATH, json=command, headers=headers | {"Idempotency-Key": "archive-second"})
                assert second.json()["status"] == "completed", second.text
                assert client.get(path + f"/{plan_id}", headers=headers).json()["current_version"] == 2
                assert client.get(path + f"/{plan_id}?version=1", headers=headers).json()["report"] == plan["report"]
                assert client.get(path + f"/{plan_id}?version=99", headers=headers).status_code == 404
                refusal = client.post(PLANNING_PATH, json=_command(profile_overrides={"age_years": 15}), headers=headers | {"Idempotency-Key": "archive-refusal"})
                assert refusal.json()["status"] != "completed"
                assert client.get(path + f"/{plan_id}", headers=headers).json()["current_version"] == 2
                from app.planning.archive_repository import SqlAlchemyPlanArchiveRepository
                original_add = SqlAlchemyPlanArchiveRepository.add_version
                def fail_after_flush(repo, version):
                    original_add(repo, version)
                    raise RuntimeError("synthetic archive failure")
                with monkeypatch.context() as patch:
                    patch.setattr(SqlAlchemyPlanArchiveRepository, "add_version", fail_after_flush)
                    failed = client.post(PLANNING_PATH, json=command, headers=headers | {"Idempotency-Key": "archive-failed-transaction"})
                    assert failed.json()["recovery_code"] == "PLAN_ARCHIVE_FAILED"
                assert client.get(path + f"/{plan_id}", headers=headers).json()["current_version"] == 2
                assert session.query(DietPlanVersion).filter_by(user_id=owner.id).count() == 2
                session.execute(delete(AgentEvent).where(AgentEvent.user_id == owner.id))
                session.commit()
                archived = client.get(path + f"/{plan_id}", headers=headers).json()
                assert archived["report"]["meals"] and archived["adjustment_thread_id"] is None
                assert len(client.get(path, headers=headers).json()["items"]) == 1
                assert client.delete(path + f"/{plan_id}", headers=headers).status_code == 204
                assert client.get(path + f"/{plan_id}", headers=headers).status_code == 404
                assert client.get(path + "/today", headers=headers).json()["plan"] is None
                rows = session.scalars(select(DietPlanVersion).where(DietPlanVersion.user_id == owner.id)).all()
                assert all(row.report is None and row.provenance is None for row in rows)
    finally:
        engine.dispose()


def test_concurrent_archive_writes_have_one_day_and_unique_versions() -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from app.planning.archive_repository import SqlAlchemyPlanArchiveRepository
    from app.planning.archive_service import PlanArchiveService
    from tests.planning.test_plan_archive import command
    from app.planning.models import DietPlan, DietPlanVersion

    settings = _settings()
    engine = create_engine(validate_test_database_configuration(settings))
    with Session(engine) as session:
        owner, _ = _create_user(session, label="archive-concurrency")
        owner_id = owner.id
    gate = Barrier(2)
    started = datetime.now(UTC)
    def write(_):
        with Session(engine) as session:
            service = PlanArchiveService(repository=SqlAlchemyPlanArchiveRepository(session))
            gate.wait(timeout=10)
            service.record_completion(command(started_at=started).model_copy(update={"user_id": owner_id}))
            session.commit()
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(write, range(2)))
        with Session(engine) as session:
            assert session.query(DietPlan).filter_by(user_id=owner_id).one().current_version == 2
            assert sorted(row.version for row in session.query(DietPlanVersion).filter_by(user_id=owner_id)) == [1, 2]
    finally:
        engine.dispose()


def test_adjustment_submission_keys_distinguish_new_intent_from_retries():
    from sqlalchemy import select, func
    from app.agent.models import AgentRun
    from app.planning.models import DietPlanVersion

    settings = _settings()
    test_url = validate_test_database_configuration(settings)
    subprocess.run([sys.executable, "scripts/run_initialized_app.py", "--prepare-only"], cwd=BACKEND_ROOT, env=_test_env(settings), check=True)
    engine = create_engine(test_url)
    try:
        with Session(engine) as session:
            owner, token = _create_user(session, label="submission-keys")
            _, other_token = _create_user(session, label="submission-other")
            authentication = AuthenticationService(repository=SqlAlchemyAuthRepository(session), secret_key=SECRET, issuer="food-agent-api", audience="food-agent-h5", commit=session.commit, rollback=session.rollback)
            app = create_app(settings)
            app.dependency_overrides[get_authentication_service] = lambda: authentication
            headers = {"Authorization": f"Bearer {token}"}
            with TestClient(app) as client:
                started = client.post(PLANNING_PATH, json=_command(), headers=headers | {"Idempotency-Key": "submission-plan"})
                assert started.status_code == 201 and started.json()["status"] == "completed", started.text
                thread_id = started.json()["thread_id"]
                path = f"/api/v1/agent/threads/{thread_id}"
                payload = {"kind": "description", "text": "午餐换一份"}
                first_headers = headers | {"Idempotency-Key": "adjustment-click-1"}
                first = client.post(path + "/input", json=payload, headers=first_headers)
                assert first.status_code == 202 and first.json()["status"] == "completed", first.text
                snapshot = client.get(path, headers=headers).json()
                repeated = client.post(path + "/input", json=payload, headers=first_headers)
                assert repeated.status_code == 202
                assert client.get(path, headers=headers).json() == snapshot
                conflict = client.post(path + "/input", json={"kind": "description", "text": "晚餐换一份"}, headers=first_headers)
                assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "COMMAND_KEY_CONFLICT"
                assert client.post(path + "/input", json=payload, headers={"Authorization": f"Bearer {other_token}", "Idempotency-Key": "adjustment-click-1"}).status_code == 404
                again = client.post(path + "/input", json=payload, headers=headers | {"Idempotency-Key": "adjustment-click-2"})
                assert again.status_code == 202 and again.json()["status"] == "completed", again.text
                changed = client.get(path, headers=headers).json()
                assert changed["revision"] > snapshot["revision"]
                before_meals, after_meals = snapshot["report"]["meals"], changed["report"]["meals"]
                assert before_meals[0] == after_meals[0] and before_meals[2] == after_meals[2]
                assert before_meals[1] != after_meals[1]
                # Replaying an older command cannot overwrite the newer checkpoint/version.
                assert client.post(path + "/input", json=payload, headers=first_headers).status_code == 202
                assert client.get(path, headers=headers).json() == changed
                assert client.post(path + "/input", json=payload, headers=headers | {"Idempotency-Key": "x" * 129}).status_code == 422
                assert session.scalar(select(func.count()).select_from(AgentRun).where(AgentRun.user_id == owner.id)) == 3
                assert session.scalar(select(func.count()).select_from(DietPlanVersion).where(DietPlanVersion.user_id == owner.id)) == 3
    finally:
        engine.dispose()
