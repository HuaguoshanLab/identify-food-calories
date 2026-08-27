"""Real PostgreSQL evidence for refresh rotation serialization and rollback."""

from __future__ import annotations

import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.auth.models import AuthSession, RefreshToken, User, UserRole
from app.auth.repository import SqlAlchemyAuthRepository
from app.auth.security import digest_refresh_token
from app.auth.service import AuthenticationService, RefreshTokenReplayed


NOW = datetime(2026, 8, 27, 10, 30, tzinfo=UTC)
SECRET = "refresh-concurrency-secret-with-at-least-forty-eight-bytes"


def _seed_refresh_family(test_engine: Engine) -> tuple[uuid.UUID, uuid.UUID, str]:
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    raw_refresh = f"seed-{uuid.uuid4().hex}"
    with Session(test_engine) as setup:
        setup.add(
            User(
                id=user_id,
                email=f"refresh-{uuid.uuid4().hex}@example.com",
                password_hash="argon2id-digest",
                role=UserRole.USER.value,
                is_active=True,
                email_verified_at=NOW,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        setup.add(
            AuthSession(
                id=session_id,
                user_id=user_id,
                family_id=uuid.uuid4(),
                created_at=NOW,
                last_seen_at=NOW,
                expires_at=NOW + timedelta(days=30),
                revoked_at=None,
                device_label=None,
            )
        )
        setup.add(
            RefreshToken(
                id=uuid.uuid4(),
                session_id=session_id,
                token_digest=digest_refresh_token(
                    secret_key=SECRET, refresh_token=raw_refresh
                ),
                issued_at=NOW,
                expires_at=NOW + timedelta(days=30),
                consumed_at=None,
                replaced_by_id=None,
                revoked_at=None,
            )
        )
        setup.commit()
    return user_id, session_id, raw_refresh


def _service(session: Session, *, commit: object | None = None) -> AuthenticationService:
    return AuthenticationService(
        repository=SqlAlchemyAuthRepository(session),
        secret_key=SECRET,
        issuer="food-agent-api",
        audience="food-agent-h5",
        now=lambda: NOW,
        commit=commit if commit is not None else session.commit,
        rollback=session.rollback,
        refresh_token_factory=lambda: f"successor-{uuid.uuid4().hex}",
    )


def _delete_family(test_engine: Engine, user_id: uuid.UUID) -> None:
    with Session(test_engine) as cleanup:
        user = cleanup.get(User, user_id)
        if user is not None:
            cleanup.delete(user)
            cleanup.commit()


def test_two_independent_postgres_transactions_have_one_rotation_winner_and_replay_revokes_family(
    test_engine: Engine,
) -> None:
    """No SQLite, in-memory fake, or sleep can prove this row-lock protocol."""

    assert test_engine.url.drivername == "postgresql+psycopg"
    user_id, session_id, raw_refresh = _seed_refresh_family(test_engine)
    barrier = Barrier(2)

    def refresh_once() -> str:
        with Session(test_engine) as session:
            service = _service(session)
            barrier.wait()
            try:
                service.refresh(raw_refresh)
                return "rotated"
            except RefreshTokenReplayed:
                return "replayed"

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(lambda _index: refresh_once(), range(2)))
        assert Counter(outcomes) == {"rotated": 1, "replayed": 1}

        with Session(test_engine) as inspection:
            tokens = list(
                inspection.scalars(
                    select(RefreshToken).where(RefreshToken.session_id == session_id)
                )
            )
            family = inspection.get(AuthSession, session_id)
            assert family is not None and family.revoked_at == NOW
            assert len(tokens) == 2
            assert sum(token.consumed_at is not None for token in tokens) == 1
            assert sum(token.replaced_by_id is not None for token in tokens) == 1
            assert all(token.revoked_at == NOW for token in tokens)
    finally:
        _delete_family(test_engine, user_id)


def test_transaction_failure_rolls_back_consumption_and_successor_without_orphan(
    test_engine: Engine,
) -> None:
    user_id, session_id, raw_refresh = _seed_refresh_family(test_engine)

    def failed_commit() -> None:
        raise RuntimeError("injected commit failure")

    try:
        with Session(test_engine) as session, pytest.raises(RuntimeError):
            _service(session, commit=failed_commit).refresh(raw_refresh)

        with Session(test_engine) as inspection:
            tokens = list(
                inspection.scalars(
                    select(RefreshToken).where(RefreshToken.session_id == session_id)
                )
            )
            assert len(tokens) == 1
            assert tokens[0].consumed_at is None
            assert tokens[0].replaced_by_id is None
            assert tokens[0].revoked_at is None
    finally:
        _delete_family(test_engine, user_id)
