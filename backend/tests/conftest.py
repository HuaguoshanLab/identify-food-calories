"""Fixtures that prevent repository tests from ever using a development database."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import Connection, Engine, create_engine
from sqlalchemy.orm import Session

from app.core.config import ConfigurationError, Settings, validate_test_database_configuration


def _guarded_test_settings() -> Settings:
    """Load test settings directly from the process; no defaults or fallbacks exist."""

    return Settings(
        app_env=os.environ.get("APP_ENV", ""),
        database_url=os.environ.get("DATABASE_URL", ""),
        test_database_url=os.environ.get("TEST_DATABASE_URL"),
        _env_file=None,
    )


def _upgrade_test_database() -> None:
    """Run migrations explicitly for the isolated target before a DB fixture is used."""

    if not Path("alembic.ini").is_file():
        raise ConfigurationError("Alembic configuration is required before database tests run")

    migration_env = os.environ.copy()
    migration_env["APP_ENV"] = "test"
    subprocess.run(["alembic", "upgrade", "head"], check=True, env=migration_env)


@pytest.fixture(scope="session")
def test_engine() -> Generator[Engine, None, None]:
    """Create a separate engine only after every isolation guard has passed."""

    test_url = validate_test_database_configuration(_guarded_test_settings())
    _upgrade_test_database()
    engine = create_engine(test_url, pool_pre_ping=True)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(test_engine: Engine) -> Generator[Session, None, None]:
    """Rollback all writes, including nested commits, after every repository test."""

    connection: Connection = test_engine.connect()
    outer_transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer_transaction.rollback()
        connection.close()
