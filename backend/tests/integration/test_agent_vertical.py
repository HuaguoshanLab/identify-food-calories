"""Real PostgreSQL vertical proof: authenticated command → graph → tools → ledger/SSE."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.agent.models import AgentEvent, AgentRun, AgentThread
from app.auth.api import get_authentication_service
from app.auth.models import AuthSession, User, UserRole
from app.auth.repository import SqlAlchemyAuthRepository
from app.auth.security import issue_access_token
from app.auth.service import AuthenticationService
from app.core.config import Settings, validate_test_database_configuration
from app.main import create_app


BACKEND_ROOT = Path(__file__).resolve().parents[2]
SECRET = "agent-vertical-test-secret-with-at-least-forty-eight-bytes"


def _settings() -> Settings:
    return Settings(
        app_env="test",
        database_url="postgresql+psycopg://postgres:postgres@localhost:5432/food_agent_dev",
        test_database_url="postgresql+psycopg://postgres:postgres@localhost:55432/food_agent_test",
        secret_key=SECRET,
        _env_file=None,
    )


def _create_user(session: Session, *, label: str) -> tuple[User, AuthSession, str]:
    now = datetime.now(UTC)
    user = User(
        id=uuid.uuid4(), email=f"agent-vertical-{label}-{uuid.uuid4().hex}@example.test",
        password_hash="argon2id-digest", role=UserRole.USER.value, is_active=True,
        email_verified_at=now, created_at=now, updated_at=now,
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
    return user, auth_session, token


def test_direct_grams_real_pg_api_sse_and_checkpoint() -> None:
    """The first GREEN proves the persisted boundary, not an in-memory or SQLite substitute."""

    settings = _settings()
    test_url = validate_test_database_configuration(settings)
    subprocess.run([sys.executable, "scripts/run_initialized_app.py", "--prepare-only"], cwd=BACKEND_ROOT, env=os.environ.copy(), check=True)
    engine = create_engine(test_url)
    try:
        with Session(engine) as session:
            user, auth_session, token = _create_user(session, label="owner")
            _other, _other_session, other_token = _create_user(session, label="other")
            authentication = AuthenticationService(
                repository=SqlAlchemyAuthRepository(session), secret_key=SECRET,
                issuer="food-agent-api", audience="food-agent-h5", commit=session.commit, rollback=session.rollback,
            )
            application = create_app(settings)
            application.dependency_overrides[get_authentication_service] = lambda: authentication
            with TestClient(application) as client:
                response = client.post("/api/v1/agent/threads", json={"input_text": "米饭 100 克"}, headers={"Authorization": f"Bearer {token}"})
                assert response.status_code == 201, response.text
                snapshot = response.json()
                assert snapshot["status"] == "completed"
                assert snapshot["report"]["totals"]["energy_kcal"] == "130.0"
                thread_id = snapshot["thread_id"]
                stream = client.get(f"/api/v1/agent/threads/{thread_id}/events", headers={"Authorization": f"Bearer {token}"})
                assert stream.status_code == 200
                assert "event: agent" in stream.text and "米饭" not in stream.text and "130.0" not in stream.text
                assert client.get(f"/api/v1/agent/threads/{thread_id}", headers={"Authorization": f"Bearer {other_token}"}).status_code == 404

            assert session.query(AgentThread).filter_by(user_id=user.id).count() == 1
            assert session.query(AgentRun).filter_by(user_id=user.id, status="completed").count() == 1
            assert session.query(AgentEvent).filter_by(user_id=user.id).count() >= 2
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM checkpoints")) >= 1
    finally:
        engine.dispose()


def test_real_pg_api_resumes_same_waiting_run_without_repeating_the_parse() -> None:
    """A public text reply resumes the same tenant-bound checkpoint, then permits a correction."""

    settings = _settings()
    test_url = validate_test_database_configuration(settings)
    subprocess.run([sys.executable, "scripts/run_initialized_app.py", "--prepare-only"], cwd=BACKEND_ROOT, env=os.environ.copy(), check=True)
    engine = create_engine(test_url)
    try:
        with Session(engine) as session:
            user, _auth_session, token = _create_user(session, label="clarification")
            authentication = AuthenticationService(
                repository=SqlAlchemyAuthRepository(session), secret_key=SECRET,
                issuer="food-agent-api", audience="food-agent-h5", commit=session.commit, rollback=session.rollback,
            )
            application = create_app(settings)
            application.dependency_overrides[get_authentication_service] = lambda: authentication
            headers = {"Authorization": f"Bearer {token}"}
            with TestClient(application) as client:
                created = client.post("/api/v1/agent/threads", json={"input_text": "米饭"}, headers=headers)
                assert created.status_code == 201, created.text
                waiting = created.json()
                assert waiting["status"] == "waiting"
                assert len(waiting["report"]["questions"]) == 1
                thread_id = waiting["thread_id"]
                first_run = session.query(AgentRun).filter_by(thread_id=uuid.UUID(thread_id)).one()
                assert first_run.model_calls == 1 and first_run.tool_calls == 0

                resumed = client.post(
                    f"/api/v1/agent/threads/{thread_id}/input",
                    json={"kind": "description", "text": "100 克"}, headers=headers,
                )
                assert resumed.status_code == 202, resumed.text
                snapshot = client.get(f"/api/v1/agent/threads/{thread_id}", headers=headers).json()
                assert snapshot["status"] == "completed"
                session.expire_all()
                same_run = session.query(AgentRun).filter_by(id=first_run.id).one()
                assert same_run.model_calls == 1 and same_run.tool_calls == 3

                correction = client.post(
                    f"/api/v1/agent/threads/{thread_id}/input",
                    json={"kind": "description", "text": '{"corrections":{"rice-1":{"grams":"150"}}}'}, headers=headers,
                )
                assert correction.status_code == 202, correction.text
                assert correction.json()["status"] == "completed", correction.text
                corrected = client.get(f"/api/v1/agent/threads/{thread_id}", headers=headers).json()
                assert corrected["report"]["totals"]["energy_kcal"] == "195.0"
                latest = session.query(AgentRun).filter_by(thread_id=uuid.UUID(thread_id)).order_by(AgentRun.created_at.desc()).first()
                assert latest is not None and latest.model_calls == 0 and latest.tool_calls == 2
                assert session.query(AgentRun).filter_by(user_id=user.id).count() == 2
    finally:
        engine.dispose()
