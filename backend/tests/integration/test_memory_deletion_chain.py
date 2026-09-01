"""Real PostgreSQL proof that memory deletion stays locally final while provider cleanup retries."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.auth.models import User, UserRole
from app.core.config import Settings, validate_test_database_configuration
from app.memory.providers import FakeMemoryProvider
from app.memory.repository import SqlAlchemyMemoryLedgerRepository
from app.memory.service import MemoryService
from app.records.models import MemoryDeletionOutbox


BACKEND_ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 8, 31, 8, 0, tzinfo=UTC)


def _settings() -> Settings:
    return Settings(app_env="test", database_url="postgresql+psycopg://postgres:postgres@localhost:5432/food_agent_dev", test_database_url="postgresql+psycopg://postgres:postgres@localhost:55432/food_agent_test", _env_file=None)


def _service(session: Session, provider: FakeMemoryProvider) -> MemoryService:
    return MemoryService(repository=SqlAlchemyMemoryLedgerRepository(session), provider=provider, now=lambda: NOW, commit=session.commit, rollback=session.rollback, retry_backoff_seconds=1)


def test_real_pg_memory_delete_is_immediately_invisible_and_retries_external_cleanup() -> None:
    settings = _settings()
    test_url = validate_test_database_configuration(settings)
    test_env = os.environ | {"APP_ENV": "test", "DATABASE_URL": settings.database_url, "TEST_DATABASE_URL": settings.test_database_url or ""}
    subprocess.run([sys.executable, "scripts/run_initialized_app.py", "--prepare-only"], cwd=BACKEND_ROOT, env=test_env, check=True)
    engine = create_engine(test_url)
    provider = FakeMemoryProvider()
    try:
        with Session(engine) as session:
            user = User(id=uuid.uuid4(), email=f"memory-delete-{uuid.uuid4().hex}@example.test", password_hash="argon2id-digest", role=UserRole.USER.value, is_active=True, email_verified_at=NOW, created_at=NOW, updated_at=NOW)
            session.add(user)
            session.commit()
            service = _service(session, provider)
            memory = service.create_direct(user_id=user.id, category="avoidance", canonical_text="不吃花生")
            assert service.process_due_provisioning() == (1, 0)
            provider.fail_next_delete = True
            service.delete_memory(memory_id=memory.id, user_id=user.id)
            assert service.list_memories(user_id=user.id) == []
            outbox = session.query(MemoryDeletionOutbox).filter_by(ledger_id=memory.id).one()
            assert outbox.status == "pending"
            assert service.process_due_deletions() == (0, 1)
            session.refresh(outbox)
            assert outbox.status == "pending" and outbox.attempt == 1
            outbox.not_before = NOW
            session.commit()
            assert service.process_due_deletions() == (1, 0)
            session.refresh(outbox)
            assert outbox.status == "completed"
    finally:
        engine.dispose()
