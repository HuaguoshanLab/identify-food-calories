"""Real PostgreSQL evidence for direct-memory provisioning recovery and isolation."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.agent.repository import SqlAlchemyAgentRepository
from app.agent.service import AgentService
from app.auth.models import User, UserRole
from app.core.config import Settings, validate_test_database_configuration
from app.memory.providers import FakeMemoryProvider
from app.memory.repository import SqlAlchemyMemoryLedgerRepository
from app.memory.service import MemoryService


BACKEND_ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)


def _settings() -> Settings:
    return Settings(
        app_env="test",
        database_url="postgresql+psycopg://postgres:postgres@localhost:5432/food_agent_dev",
        test_database_url="postgresql+psycopg://postgres:postgres@localhost:55432/food_agent_test",
        _env_file=None,
    )


def _prepare() -> tuple[object, FakeMemoryProvider]:
    settings = _settings()
    test_url = validate_test_database_configuration(settings)
    subprocess.run(
        [sys.executable, "scripts/run_initialized_app.py", "--prepare-only"],
        cwd=BACKEND_ROOT,
        env=os.environ.copy(),
        check=True,
    )
    return create_engine(test_url), FakeMemoryProvider()


def _service(session: Session, provider: FakeMemoryProvider, now: datetime = NOW) -> MemoryService:
    return MemoryService(
        repository=SqlAlchemyMemoryLedgerRepository(session),
        provider=provider,
        now=lambda: now,
        commit=session.commit,
        rollback=session.rollback,
        retry_backoff_seconds=1,
    )


def _user_and_run(session: Session) -> tuple[User, uuid.UUID]:
    user = User(
        id=uuid.uuid4(),
        email=f"direct-memory-{uuid.uuid4().hex}@example.test",
        password_hash="argon2id-digest",
        role=UserRole.USER.value,
        is_active=True,
        email_verified_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )
    session.add(user)
    session.commit()
    agent = AgentService(
        repository=SqlAlchemyAgentRepository(session),
        now=lambda: NOW,
        commit=session.commit,
        rollback=session.rollback,
    )
    thread = agent.create_thread(user_id=user.id)
    run = agent.create_or_reuse_run(
        thread_id=thread.id,
        user_id=user.id,
        command_key=f"direct-memory-{uuid.uuid4().hex}",
        canonical_command={"input_text": "我不吃辣"},
    )
    return user, run.id


def test_pg_concurrent_capture_creates_one_ledger_intent_and_remote_record() -> None:
    engine, provider = _prepare()
    try:
        with Session(engine) as session:
            user, run_id = _user_and_run(session)
        barrier = Barrier(2)

        def capture() -> uuid.UUID:
            with Session(engine) as session:
                barrier.wait(timeout=5)
                memory = _service(session, provider).create_direct(
                    user_id=user.id,
                    source_run_id=run_id,
                    category="avoidance",
                    canonical_text="不吃辣",
                )
                return memory.id

        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = pool.map(lambda _index: capture(), range(2))
        assert first == second
        with Session(engine) as session:
            service = _service(session, provider)
            assert service.process_due_provisioning() == (1, 0)
            assert session.execute(
                text("SELECT count(*) FROM preference_memory_ledger WHERE user_id = :user_id"),
                {"user_id": user.id},
            ).scalar_one() == 1
            assert session.execute(
                text("SELECT count(*) FROM memory_provision_outbox WHERE user_id = :user_id"),
                {"user_id": user.id},
            ).scalar_one() == 1
        assert len(provider.direct_records) == 1
    finally:
        engine.dispose()


def test_outcome_unknown_restart_resolves_exact_key_without_a_second_create() -> None:
    class OutcomeUnknownAfterCreate(FakeMemoryProvider):
        def __init__(self) -> None:
            super().__init__()
            self.create_count = 0

        def create_direct(self, **kwargs: object) -> str:  # type: ignore[override]
            self.create_count += 1
            external_id = super().create_direct(**kwargs)  # type: ignore[arg-type]
            if self.create_count == 1:
                raise TimeoutError("provider outcome unknown after commit")
            return external_id

    engine, _provider = _prepare()
    provider = OutcomeUnknownAfterCreate()
    try:
        with Session(engine) as session:
            user, run_id = _user_and_run(session)
            memory = _service(session, provider).create_direct(
                user_id=user.id,
                source_run_id=run_id,
                category="avoidance",
                canonical_text="不吃辣",
            )
            assert _service(session, provider).process_due_provisioning() == (0, 1)
        # A rebuilt worker receives only the durable intent and resolves its exact opaque key.
        with Session(engine) as restarted:
            assert _service(restarted, provider, NOW + timedelta(seconds=1)).process_due_provisioning() == (1, 0)
            recovered = _service(restarted, provider).get_memory(memory_id=memory.id, user_id=user.id)
            assert recovered.external_memory_id is not None
        assert provider.create_count == 1
        assert len(provider.direct_records) == 1
    finally:
        engine.dispose()


def test_delete_races_leave_no_local_or_remote_memory_and_isolate_users() -> None:
    engine, provider = _prepare()
    try:
        with Session(engine) as session:
            owner, run_id = _user_and_run(session)
            other, other_run_id = _user_and_run(session)
            owner_memory = _service(session, provider).create_direct(
                user_id=owner.id,
                source_run_id=run_id,
                category="avoidance",
                canonical_text="不吃辣",
            )
            other_memory = _service(session, provider).create_direct(
                user_id=other.id,
                source_run_id=other_run_id,
                category="avoidance",
                canonical_text="不吃辣",
            )
            _service(session, provider).delete_memory(memory_id=owner_memory.id, user_id=owner.id)
            assert _service(session, provider).process_due_provisioning() == (1, 0)
            assert _service(session, provider).process_due_deletions() == (0, 0)
            assert _service(session, provider).list_memories(user_id=owner.id) == []
            assert [memory.id for memory in _service(session, provider).list_memories(user_id=other.id)] == [other_memory.id]
        assert len(provider.direct_records) == 1
    finally:
        engine.dispose()
