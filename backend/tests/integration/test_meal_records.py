"""Real PostgreSQL proof for confirmed meal snapshots and tenant isolation."""

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

from app.admin.repository import SqlAlchemyAdminRepository
from app.admin.schemas import RuntimeConfigCommand
from app.admin.service import AdminService
from app.agent.models import AgentThread
from app.auth.api import get_authentication_service
from app.auth.models import AuthSession, User, UserRole
from app.auth.repository import SqlAlchemyAuthRepository
from app.auth.security import issue_access_token
from app.auth.service import AuthenticationService
from app.core.config import Settings, validate_test_database_configuration
from app.main import create_app
from app.records.api import get_meal_record_service
from app.records.repository import SqlAlchemyMealRecordRepository
from app.records.service import MealRecordService


BACKEND_ROOT = Path(__file__).resolve().parents[2]
SECRET = "meal-record-integration-secret-with-at-least-forty-eight-bytes"


def _settings() -> Settings:
    return Settings(app_env="test", database_url="postgresql+psycopg://postgres:postgres@localhost:5432/food_agent_dev", test_database_url="postgresql+psycopg://postgres:postgres@localhost:55432/food_agent_test", secret_key=SECRET, _env_file=None)


def _create_user(session: Session, *, label: str) -> tuple[User, str]:
    now = datetime.now(UTC)
    user = User(id=uuid.uuid4(), email=f"meal-record-{label}-{uuid.uuid4().hex}@example.test", password_hash="argon2id-digest", role=UserRole.USER.value, is_active=True, email_verified_at=now, created_at=now, updated_at=now)
    auth_session = AuthSession(id=uuid.uuid4(), user_id=user.id, family_id=uuid.uuid4(), created_at=now, last_seen_at=now, expires_at=now + timedelta(days=30))
    session.add_all([user, auth_session])
    session.commit()
    token, _ = issue_access_token(secret_key=SECRET, user_id=user.id, role=UserRole.USER.value, issuer="food-agent-api", audience="food-agent-h5", issued_at=now, session_id=auth_session.id)
    return user, token


def _enable_test_runtime_config(session: Session) -> None:
    """Admit the fake test provider through the same audited policy path as production."""

    if SqlAlchemyAdminRepository(session).get_active_runtime_config() is not None:
        return
    now = datetime.now(UTC)
    actor = User(
        id=uuid.uuid4(), email=f"runtime-admin-{uuid.uuid4().hex}@example.test", password_hash="argon2id-digest",
        role=UserRole.ADMIN.value, is_active=True, email_verified_at=now, created_at=now, updated_at=now,
    )
    session.add(actor)
    session.flush()
    AdminService(
        repository=SqlAlchemyAdminRepository(session), now=lambda: now, commit=session.commit, rollback=session.rollback,
    ).configure_runtime(
        actor_user_id=actor.id,
        command=RuntimeConfigCommand(
            provider="deepseek", model_alias="deepseek-v4-flash", enabled=True,
            single_call_cap_usd="0.03", period_cap_usd="3.00", input_usd_per_m="0.20", output_usd_per_m="0.80",
            reason="test runtime policy", confirm=True,
        ),
        command_key="test-meal-record-runtime-config-0001",
    )


def test_completed_report_can_be_confirmed_updated_and_deleted_without_deleting_thread() -> None:
    settings = _settings()
    test_url = validate_test_database_configuration(settings)
    test_env = os.environ | {
        "APP_ENV": "test",
        "DATABASE_URL": settings.database_url,
        "TEST_DATABASE_URL": settings.test_database_url or "",
    }
    subprocess.run([sys.executable, "scripts/run_initialized_app.py", "--prepare-only"], cwd=BACKEND_ROOT, env=test_env, check=True)
    engine = create_engine(test_url)
    try:
        with Session(engine) as session:
            owner, owner_token = _create_user(session, label="owner")
            _other, other_token = _create_user(session, label="other")
            _enable_test_runtime_config(session)
            authentication = AuthenticationService(repository=SqlAlchemyAuthRepository(session), secret_key=SECRET, issuer="food-agent-api", audience="food-agent-h5", commit=session.commit, rollback=session.rollback)
            application = create_app(settings)
            application.dependency_overrides[get_authentication_service] = lambda: authentication
            application.dependency_overrides[get_meal_record_service] = lambda: MealRecordService(repository=SqlAlchemyMealRecordRepository(session), commit=session.commit, rollback=session.rollback)
            headers = {"Authorization": f"Bearer {owner_token}"}
            with TestClient(application) as client:
                analyzed = client.post("/api/v1/agent/threads", json={"input_text": "米饭 100 克"}, headers=headers)
                assert analyzed.status_code == 201, analyzed.text
                thread_id = analyzed.json()["thread_id"]
                report_catalog_version = analyzed.json()["report"]["items"][0]["catalog_version"]
                saved = client.post("/api/v1/meal-records", json={"thread_id": thread_id, "command_key": "save-key-00000001", "time_zone": "UTC", "meal_slot": "breakfast"}, headers=headers)
                assert saved.status_code == 201, saved.text
                record = saved.json()
                assert record["meal_slot"] == "breakfast"
                assert record["energy_kcal"] == "130.000000" and record["nutrition_catalog_version"] == report_catalog_version
                repeated = client.post("/api/v1/meal-records", json={"thread_id": thread_id, "command_key": "save-key-00000001", "time_zone": "UTC", "meal_slot": "breakfast"}, headers=headers)
                assert repeated.status_code == 201 and repeated.json()["id"] == record["id"]
                assert client.get(f"/api/v1/meal-records/{record['id']}", headers={"Authorization": f"Bearer {other_token}"}).status_code == 404
                changed_time = (datetime.now(UTC) - timedelta(days=1)).isoformat()
                updated = client.patch(f"/api/v1/meal-records/{record['id']}", json={"consumed_at": changed_time, "time_zone": "UTC"}, headers=headers)
                assert updated.status_code == 200 and updated.json()["id"] == record["id"] and updated.json()["energy_kcal"] == record["energy_kcal"]
                assert updated.json()["meal_slot"] == "breakfast"
                changed_slot = client.patch(f"/api/v1/meal-records/{record['id']}", json={"consumed_at": changed_time, "time_zone": "UTC", "meal_slot": "snack"}, headers=headers)
                assert changed_slot.status_code == 200 and changed_slot.json()["meal_slot"] == "snack"
                assert client.get(f"/api/v1/meal-records/{record['id']}", headers=headers).json()["meal_slot"] == "snack"
                assert client.patch(f"/api/v1/meal-records/{record['id']}", json={"consumed_at": changed_time, "time_zone": "UTC", "meal_slot": "dinner"}, headers={"Authorization": f"Bearer {other_token}"}).status_code == 404
                assert client.delete(f"/api/v1/meal-records/{record['id']}", headers=headers).status_code == 204
                assert client.get(f"/api/v1/meal-records/{record['id']}", headers=headers).status_code == 404
            assert session.get(AgentThread, uuid.UUID(thread_id)) is not None
            assert session.query(AgentThread).filter_by(user_id=owner.id).count() == 1
    finally:
        engine.dispose()
