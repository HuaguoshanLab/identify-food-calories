"""Real PostgreSQL proof for D-18's lifespan-owned retention scheduler."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.agent.supervisor import PostgresLeaseSupervisor
from app.agent.retention import _RETENTION_ADVISORY_LOCK_KEY
from app.auth.api import get_authentication_service
from app.auth.models import AuthSession, User, UserRole
from app.auth.repository import SqlAlchemyAuthRepository
from app.auth.security import issue_access_token
from app.auth.service import AuthenticationService
from app.core.config import Settings, validate_test_database_configuration
from app.main import PersistedAgentRuntimeFactory, create_app


BACKEND_ROOT = Path(__file__).resolve().parents[2]
SECRET = "agent-retention-test-secret-with-at-least-forty-eight-bytes"


@dataclass
class FakeClock:
    value: datetime

    def now(self) -> datetime:
        return self.value

    def set(self, value: datetime) -> None:
        self.value = value


def _settings() -> Settings:
    return Settings(
        app_env="test",
        database_url="postgresql+psycopg://postgres:postgres@localhost:5432/food_agent_dev",
        test_database_url="postgresql+psycopg://postgres:postgres@localhost:55432/food_agent_test",
        secret_key=SECRET,
        retention_checkpoint_event_days=7,
        retention_audit_days=30,
        retention_deletion_sla_hours=24,
        retention_poll_interval_seconds=300,
        _env_file=None,
    )


def _create_user(session: Session, *, label: str) -> tuple[User, str]:
    now = datetime.now(UTC)
    user = User(
        id=uuid.uuid4(),
        email=f"agent-retention-{label}-{uuid.uuid4().hex}@example.test",
        password_hash="argon2id-digest",
        role=UserRole.USER.value,
        is_active=True,
        email_verified_at=now,
        created_at=now,
        updated_at=now,
    )
    auth_session = AuthSession(
        id=uuid.uuid4(),
        user_id=user.id,
        family_id=uuid.uuid4(),
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(days=30),
    )
    session.add_all([user, auth_session])
    session.commit()
    token, _ = issue_access_token(
        secret_key=SECRET,
        user_id=user.id,
        role=UserRole.USER.value,
        issuer="food-agent-api",
        audience="food-agent-h5",
        issued_at=now,
        session_id=auth_session.id,
    )
    return user, token


def _wait_for_automatic_sweep(client: TestClient, worker: object, *, after: int) -> int:
    """Wait for the lifespan task; this deliberately does not call a cleanup API."""

    return client.portal.call(  # type: ignore[no-any-return,union-attr]
        lambda: worker.wait_for_sweep(after=after)
    )


def test_lifespan_retention_enforces_exact_boundaries_and_tenant_isolation() -> None:
    """No direct cleanup call: FastAPI owns worker start, wake and durable retention work."""

    if os.environ.get("APP_ENV") != "test":
        return
    settings = _settings()
    test_url = validate_test_database_configuration(settings)
    subprocess.run(
        [sys.executable, "scripts/run_initialized_app.py", "--prepare-only"],
        cwd=BACKEND_ROOT,
        env=os.environ.copy(),
        check=True,
    )
    engine = create_engine(test_url)
    try:
        with Session(engine) as session:
            owner, owner_token = _create_user(session, label="owner")
            other, other_token = _create_user(session, label="other")
            authentication = AuthenticationService(
                repository=SqlAlchemyAuthRepository(session),
                secret_key=SECRET,
                issuer="food-agent-api",
                audience="food-agent-h5",
                commit=session.commit,
                rollback=session.rollback,
            )
            clock = FakeClock(datetime.now(UTC))
            application = create_app(
                settings,
                runtime_factory=PersistedAgentRuntimeFactory(settings, retention_now=clock.now),
            )
            application.dependency_overrides[get_authentication_service] = lambda: authentication
            with TestClient(application) as client:
                owner_headers = {"Authorization": f"Bearer {owner_token}"}
                other_headers = {"Authorization": f"Bearer {other_token}"}
                owner_created = client.post(
                    "/api/v1/agent/threads",
                    json={"input_text": "米饭 100 克"},
                    headers=owner_headers,
                )
                other_created = client.post(
                    "/api/v1/agent/threads",
                    json={"input_text": "米饭 100 克"},
                    headers=other_headers,
                )
                assert owner_created.status_code == 201, owner_created.text
                assert other_created.status_code == 201, other_created.text
                owner_thread = uuid.UUID(owner_created.json()["thread_id"])
                other_thread = uuid.UUID(other_created.json()["thread_id"])
                worker = cast_worker(application)

                deletion = client.delete(
                    f"/api/v1/agent/threads/{owner_thread}", headers=owner_headers
                )
                assert deletion.status_code == 202, deletion.text
                requested_at, purge_after = session.execute(
                    text(
                        "SELECT requested_at, purge_after FROM agent_deletion_intents "
                        "WHERE thread_id = :thread_id AND user_id = :user_id"
                    ),
                    {"thread_id": owner_thread, "user_id": owner.id},
                ).one()
                assert purge_after == requested_at + timedelta(hours=24, minutes=-5)
                # Before due_at no automatic cycle may remove the user-owned namespace.
                clock.set(purge_after - timedelta(microseconds=1))
                before_due = worker.completed_sweeps
                worker.wake()
                _wait_for_automatic_sweep(client, worker, after=before_due)
                assert session.execute(
                    text("SELECT count(*) FROM agent_threads WHERE id = :thread_id"),
                    {"thread_id": owner_thread},
                ).scalar_one() == 1

                clock.set(purge_after)
                at_due = worker.completed_sweeps
                worker.wake()
                _wait_for_automatic_sweep(client, worker, after=at_due)
                session.expire_all()
                assert session.execute(
                    text("SELECT count(*) FROM agent_threads WHERE id = :thread_id"),
                    {"thread_id": owner_thread},
                ).scalar_one() == 0
                assert session.execute(
                    text("SELECT count(*) FROM checkpoints WHERE thread_id = :thread_id"),
                    {"thread_id": str(owner_thread)},
                ).scalar_one() == 0
                # A second tenant must remain completely untouched by the owner's cascade.
                assert session.execute(
                    text("SELECT count(*) FROM agent_threads WHERE id = :thread_id AND user_id = :user_id"),
                    {"thread_id": other_thread, "user_id": other.id},
                ).scalar_one() == 1
                assert session.execute(
                    text("SELECT count(*) FROM checkpoints WHERE thread_id = :thread_id"),
                    {"thread_id": str(other_thread)},
                ).scalar_one() == 1

                activity = clock.now()
                session.execute(
                    text("UPDATE agent_threads SET last_activity_at = :activity WHERE id = :thread_id"),
                    {"activity": activity, "thread_id": other_thread},
                )
                session.commit()
                clock.set(activity + timedelta(days=7) - timedelta(microseconds=1))
                before_checkpoint_boundary = worker.completed_sweeps
                worker.wake()
                _wait_for_automatic_sweep(client, worker, after=before_checkpoint_boundary)
                assert session.execute(
                    text("SELECT count(*) FROM agent_events WHERE thread_id = :thread_id"),
                    {"thread_id": other_thread},
                ).scalar_one() > 0

                clock.set(activity + timedelta(days=7))
                at_checkpoint_boundary = worker.completed_sweeps
                worker.wake()
                _wait_for_automatic_sweep(client, worker, after=at_checkpoint_boundary)
                assert session.execute(
                    text("SELECT count(*) FROM agent_events WHERE thread_id = :thread_id"),
                    {"thread_id": other_thread},
                ).scalar_one() == 0
                assert session.execute(
                    text("SELECT count(*) FROM checkpoints WHERE thread_id = :thread_id"),
                    {"thread_id": str(other_thread)},
                ).scalar_one() == 0

                run_id = session.execute(
                    text("SELECT id FROM agent_runs WHERE thread_id = :thread_id"),
                    {"thread_id": other_thread},
                ).scalar_one()
                updated_at = clock.now()
                session.execute(
                    text("UPDATE agent_runs SET updated_at = :updated_at WHERE id = :run_id"),
                    {"updated_at": updated_at, "run_id": run_id},
                )
                session.commit()
                clock.set(updated_at + timedelta(days=30) - timedelta(microseconds=1))
                before_audit_boundary = worker.completed_sweeps
                worker.wake()
                _wait_for_automatic_sweep(client, worker, after=before_audit_boundary)
                assert session.execute(
                    text("SELECT count(*) FROM agent_runs WHERE id = :run_id"),
                    {"run_id": run_id},
                ).scalar_one() == 1

                clock.set(updated_at + timedelta(days=30))
                at_audit_boundary = worker.completed_sweeps
                worker.wake()
                _wait_for_automatic_sweep(client, worker, after=at_audit_boundary)
                assert session.execute(
                    text("SELECT count(*) FROM agent_runs WHERE id = :run_id"),
                    {"run_id": run_id},
                ).scalar_one() == 0
    finally:
        engine.dispose()


def cast_worker(application: object):
    runtime = application.state.agent_runtime
    supervisor = runtime.supervisor
    assert isinstance(supervisor, PostgresLeaseSupervisor)
    worker = supervisor.retention_worker
    assert worker is not None
    return worker


def test_postgres_retention_lease_allows_one_worker_and_recovers_after_connection_loss() -> None:
    """A database lease, unlike an in-memory lock, survives multi-worker deployment safely."""

    if os.environ.get("APP_ENV") != "test":
        return
    test_url = validate_test_database_configuration(_settings())
    subprocess.run(
        [sys.executable, "scripts/run_initialized_app.py", "--prepare-only"],
        cwd=BACKEND_ROOT,
        env=os.environ.copy(),
        check=True,
    )
    engine = create_engine(test_url)
    first = Session(engine)
    second = Session(engine)
    try:
        assert first.scalar(
            text("SELECT pg_try_advisory_lock(:lock_key)"),
            {"lock_key": _RETENTION_ADVISORY_LOCK_KEY},
        ) is True
        assert second.scalar(
            text("SELECT pg_try_advisory_lock(:lock_key)"),
            {"lock_key": _RETENTION_ADVISORY_LOCK_KEY},
        ) is False
        # Closing the first worker's DB connection models a process crash: PostgreSQL releases
        # its session advisory locks, so another worker can resume without a manual repair.
        first.close()
        assert second.scalar(
            text("SELECT pg_try_advisory_lock(:lock_key)"),
            {"lock_key": _RETENTION_ADVISORY_LOCK_KEY},
        ) is True
    finally:
        first.close()
        second.close()
        engine.dispose()
