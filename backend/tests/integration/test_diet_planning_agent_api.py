"""Public PostgreSQL contracts for the tenant-bound diet-planning command."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta
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
from app.records.models import PreferenceMemoryLedger
from app.planning.models import PlanningProfile


BACKEND_ROOT = Path(__file__).resolve().parents[2]
SECRET = "diet-planning-agent-api-secret-with-at-least-forty-eight-bytes"
PLANNING_PATH = "/api/v1/agent/threads/diet-planning"


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
    now = datetime.now(UTC)
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
    token, _ = issue_access_token(
        secret_key=SECRET, user_id=user.id, role=UserRole.USER.value,
        issuer="food-agent-api", audience="food-agent-h5", issued_at=now, session_id=auth_session.id,
    )
    return user, token


def _command(*, confirmed: bool = True, save_profile: bool = True) -> dict[str, object]:
    return {
        "profile": {
            "height_cm": "170",
            "weight_kg": "65",
            "age_years": 30,
            "formula_variant": "mifflin_st_jeor_female",
            "activity_level": "moderate",
            "goal": "loss",
            "goal_speed": "gradual_loss",
        },
        "preferences": {
            "confirmed": confirmed,
            "exclusions": ["花生"],
            "taste_preferences": ["清淡"],
        },
        "save_profile": save_profile,
    }


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
                assert '"summary"' in stream.text

            assert session.query(PlanningProfile).filter_by(user_id=owner.id, deleted_at=None).count() == 1
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
            assert len(captured) == 1
    finally:
        engine.dispose()
