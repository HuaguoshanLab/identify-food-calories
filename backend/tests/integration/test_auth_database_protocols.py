"""Real PostgreSQL evidence for auth migrations, constraints, and login throttling."""

from __future__ import annotations

import hashlib
import hmac
import os
import subprocess
import sys
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import pytest
from sqlalchemy import Engine, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import (
    AuthSession,
    LoginAttempt,
    RefreshToken,
    User,
    UserRole,
    VerificationChallenge,
)
from app.auth.repository import SqlAlchemyAuthRepository
from app.auth.security import hash_password
from app.auth.service import AuthenticationService, InvalidCredentials, LoginRateLimited


NOW = datetime(2026, 8, 27, 10, 0, tzinfo=UTC)
SECRET = "postgres-rate-limit-secret-with-at-least-forty-eight-bytes"
PASSWORD = "correct horse battery staple"


def _alembic(*arguments: str) -> None:
    environment = os.environ.copy()
    environment["APP_ENV"] = "test"
    subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        check=True,
        env=environment,
    )


def test_empty_database_upgrades_0001_to_0002_and_downgrades_cleanly(
    test_engine: Engine,
) -> None:
    try:
        _alembic("downgrade", "base")
        assert set(inspect(test_engine).get_table_names(schema="public")) == {
            "alembic_version"
        }

        _alembic("upgrade", "0001")
        tables_at_0001 = set(inspect(test_engine).get_table_names(schema="public"))
        assert "users" in tables_at_0001
        assert "login_attempts" not in tables_at_0001

        _alembic("upgrade", "0002")
        assert "login_attempts" in set(
            inspect(test_engine).get_table_names(schema="public")
        )
        with test_engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0002"

        _alembic("downgrade", "0001")
        assert "login_attempts" not in set(
            inspect(test_engine).get_table_names(schema="public")
        )
        with test_engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0001"
    finally:
        # Migration tests must restore head even when an intermediate assertion fails.
        _alembic("upgrade", "head")


def test_constraints_and_savepoint_rollback_are_enforced_by_postgres(
    db_session: Session,
) -> None:
    with db_session.begin_nested() as savepoint:
        transient = User(
            id=uuid.uuid4(),
            email=f"transient-{uuid.uuid4().hex}@example.com",
            password_hash="argon2id-digest",
            role=UserRole.USER.value,
            is_active=True,
            created_at=NOW,
            updated_at=NOW,
        )
        db_session.add(transient)
        db_session.flush()
        savepoint.rollback()
    assert db_session.get(User, transient.id) is None

    invalid_email = User(
        id=uuid.uuid4(),
        email="Not-Normalized@example.com",
        password_hash="argon2id-digest",
        role=UserRole.USER.value,
        is_active=True,
        created_at=NOW,
        updated_at=NOW,
    )
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(invalid_email)
        db_session.flush()

    repository = SqlAlchemyAuthRepository(db_session)
    user = repository.add_user(
        User(
            id=uuid.uuid4(),
            email=f"protocol-{uuid.uuid4().hex}@example.com",
            password_hash="argon2id-digest",
            role=UserRole.USER.value,
            is_active=True,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    repository.add_challenge(
        VerificationChallenge(
            id=uuid.uuid4(),
            user_id=user.id,
            purpose="registration",
            context_digest=uuid.uuid4().hex,
            code_digest=uuid.uuid4().hex,
            created_at=NOW,
            expires_at=NOW + timedelta(minutes=10),
            attempts=0,
            max_attempts=5,
            resend_available_at=NOW + timedelta(seconds=60),
        )
    )
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(
            VerificationChallenge(
                id=uuid.uuid4(),
                user_id=user.id,
                purpose="registration",
                context_digest=uuid.uuid4().hex,
                code_digest=uuid.uuid4().hex,
                created_at=NOW,
                expires_at=NOW + timedelta(minutes=10),
                attempts=0,
                max_attempts=5,
                resend_available_at=NOW + timedelta(seconds=60),
            )
        )
        db_session.flush()

    auth_session = repository.add_session(
        AuthSession(
            id=uuid.uuid4(),
            user_id=user.id,
            family_id=uuid.uuid4(),
            created_at=NOW,
            last_seen_at=NOW,
            expires_at=NOW + timedelta(days=30),
        )
    )
    token_digest = uuid.uuid4().hex
    repository.add_refresh_token(
        RefreshToken(
            id=uuid.uuid4(),
            session_id=auth_session.id,
            token_digest=token_digest,
            issued_at=NOW,
            expires_at=NOW + timedelta(days=30),
        )
    )
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(
            RefreshToken(
                id=uuid.uuid4(),
                session_id=auth_session.id,
                token_digest=token_digest,
                issued_at=NOW,
                expires_at=NOW + timedelta(days=30),
            )
        )
        db_session.flush()


def _bucket_digest(scope: str, value: str) -> str:
    return hmac.new(
        SECRET.encode("utf-8"),
        f"login-{scope}:v1:{value}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def test_concurrent_failures_create_one_lockout_then_clock_and_success_reset(
    test_engine: Engine,
) -> None:
    email = f"concurrent-{uuid.uuid4().hex}@example.com"
    source = f"test-source-{uuid.uuid4().hex}"
    user_id = uuid.uuid4()
    with Session(test_engine) as setup:
        setup.add(
            User(
                id=user_id,
                email=email,
                password_hash=hash_password(PASSWORD),
                role=UserRole.USER.value,
                is_active=True,
                email_verified_at=NOW,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        setup.commit()

    barrier = Barrier(5)

    def fail_once() -> str:
        with Session(test_engine) as session:
            service = AuthenticationService(
                repository=SqlAlchemyAuthRepository(session),
                secret_key=SECRET,
                issuer="food-agent-api",
                audience="food-agent-h5",
                now=lambda: NOW,
                commit=session.commit,
                rollback=session.rollback,
            )
            barrier.wait()
            try:
                service.login(email=email, password="wrong password value", source=source)
            except LoginRateLimited:
                return "limited"
            except InvalidCredentials:
                return "invalid"
        raise AssertionError("wrong password unexpectedly authenticated")

    with ThreadPoolExecutor(max_workers=5) as executor:
        outcomes = list(executor.map(lambda _index: fail_once(), range(5)))
    assert Counter(outcomes) == {"invalid": 4, "limited": 1}

    digests = (
        _bucket_digest("principal", email),
        _bucket_digest("source", source),
    )
    with Session(test_engine) as inspection:
        rows = list(
            inspection.scalars(
                select(LoginAttempt).where(LoginAttempt.bucket_digest.in_(digests))
            )
        )
        assert len(rows) == 2
        assert {row.failed_attempts for row in rows} == {5}
        assert all(row.blocked_until == NOW + timedelta(minutes=5) for row in rows)
        serialized = " ".join(row.bucket_digest for row in rows)
        assert email not in serialized
        assert source not in serialized

    later = NOW + timedelta(minutes=5, seconds=1)
    with Session(test_engine) as session:
        service = AuthenticationService(
            repository=SqlAlchemyAuthRepository(session),
            secret_key=SECRET,
            issuer="food-agent-api",
            audience="food-agent-h5",
            now=lambda: later,
            commit=session.commit,
            rollback=session.rollback,
        )
        with pytest.raises(InvalidCredentials):
            service.login(email=email, password="wrong password value", source=source)
        rows = list(
            session.scalars(
                select(LoginAttempt).where(LoginAttempt.bucket_digest.in_(digests))
            )
        )
        assert {row.failed_attempts for row in rows} == {1}
        assert all(row.blocked_until is None for row in rows)

        service.login(email=email, password=PASSWORD, source=source)
        assert not list(
            session.scalars(
                select(LoginAttempt).where(LoginAttempt.bucket_digest.in_(digests))
            )
        )
        session.delete(session.get(User, user_id))
        session.commit()
