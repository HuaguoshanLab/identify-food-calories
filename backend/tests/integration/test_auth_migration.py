"""Real-PostgreSQL evidence for the auth migration chain and repository adapter."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import AuthSession, RefreshToken, User, VerificationChallenge
from app.auth.repository import SqlAlchemyAuthRepository
from app.core.config import Settings, validate_test_database_configuration


def _test_url() -> str:
    settings = Settings(
        app_env=os.environ.get("APP_ENV", ""),
        database_url=os.environ.get("DATABASE_URL", ""),
        test_database_url=os.environ.get("TEST_DATABASE_URL"),
        _env_file=None,
    )
    return validate_test_database_configuration(settings)


def _alembic(*arguments: str) -> None:
    environment = os.environ.copy()
    environment["APP_ENV"] = "test"
    subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        check=True,
        env=environment,
    )


def _public_tables(database_url: str) -> set[str]:
    engine = create_engine(database_url)
    try:
        return set(inspect(engine).get_table_names(schema="public"))
    finally:
        engine.dispose()


def test_auth_migrations_rebuild_an_empty_isolated_database() -> None:
    test_url = _test_url()
    development_url = os.environ["DATABASE_URL"]
    development_tables_before = _public_tables(development_url)
    _alembic("downgrade", "base")
    _alembic("upgrade", "head")

    engine = create_engine(test_url)
    try:
        inspector = inspect(engine)
        assert {
            "users",
            "verification_challenges",
            "auth_sessions",
            "refresh_tokens",
            "login_attempts",
        } <= set(inspector.get_table_names())
        assert {item["name"] for item in inspector.get_check_constraints("users")} == {
            "ck_users_email_normalized",
            "ck_users_role",
        }
        assert {
            item["name"]
            for item in inspector.get_check_constraints("verification_challenges")
        } >= {
            "ck_verification_challenges_attempts",
            "ck_verification_challenges_expiry",
            "ck_verification_challenges_terminal_state",
        }
        assert {
            item["name"] for item in inspector.get_indexes("verification_challenges")
        } >= {"uq_verification_challenges_current"}
        assert {item["name"] for item in inspector.get_unique_constraints("refresh_tokens")} >= {
            "uq_refresh_tokens_token_digest"
        }
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0002"
    finally:
        engine.dispose()
    assert _public_tables(development_url) == development_tables_before


def test_repository_flushes_without_committing_and_database_enforces_contracts(
    db_session: Session,
) -> None:
    repository = SqlAlchemyAuthRepository(db_session)
    now = datetime.now(UTC)
    user = repository.add_user(
        User(
            email="person@example.com",
            password_hash="argon2id-digest",
            role="user",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
    )
    auth_session = repository.add_session(
        AuthSession(
            user_id=user.id,
            family_id=uuid.uuid4(),
            created_at=now,
            last_seen_at=now,
            expires_at=now + timedelta(days=30),
        )
    )
    challenge = repository.add_challenge(
        VerificationChallenge(
            user_id=user.id,
            purpose="registration",
            context_digest="context-a",
            code_digest="code-a",
            created_at=now,
            expires_at=now + timedelta(minutes=10),
            attempts=0,
            max_attempts=5,
            resend_available_at=now + timedelta(seconds=60),
        )
    )
    refresh = repository.add_refresh_token(
        RefreshToken(
            session_id=auth_session.id,
            token_digest="refresh-a",
            issued_at=now,
            expires_at=now + timedelta(days=30),
        )
    )

    assert db_session.in_transaction()
    assert repository.get_user_by_email("person@example.com") is user
    assert repository.get_current_challenge_for_update(
        context_digest="context-a", purpose="registration"
    ) is challenge
    assert repository.get_refresh_token_for_update("refresh-a") is refresh

    db_session.add(
        User(
            email="Person@example.com",
            password_hash="argon2id-digest",
            role="user",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
