"""Direct evidence that unsafe database test configuration is rejected."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import ConfigurationError, Settings, validate_test_database_configuration


TEST_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/food_calories_test"
DEV_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/food_calories_dev"
COMPOSE_DEV_URL = "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/food_agent_dev"
COMPOSE_TEST_URL = "postgresql+psycopg://postgres:postgres@127.0.0.1:55432/food_agent_test"
RUN_PG = Path(__file__).parents[1] / "run_pg.py"


def _write_test_environment(path: Path, **overrides: str) -> Path:
    values = {
        "APP_ENV": "test",
        "DATABASE_URL": COMPOSE_DEV_URL,
        "TEST_DATABASE_URL": COMPOSE_TEST_URL,
    }
    values.update(overrides)
    path.write_text("\n".join(f"{name}={value}" for name, value in values.items()) + "\n")
    return path


def _run_pg(env_file: Path, command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(RUN_PG),
            "--env-file",
            str(env_file),
            "--",
            sys.executable,
            "-c",
            command,
        ],
        check=False,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"TEST_DATABASE_URL": COMPOSE_DEV_URL}, "must not target the same database"),
        ({"TEST_DATABASE_URL": "sqlite+pysqlite:///:memory:"}, "PostgreSQL"),
        ({"TEST_DATABASE_URL": "postgresql://postgres:postgres@127.0.0.1:55432/food_agent_test"}, "psycopg"),
        ({"TEST_DATABASE_URL": "postgresql+psycopg://postgres:postgres@db:55432/food_agent_test"}, "loopback"),
        ({"TEST_DATABASE_URL": "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/food_agent_test"}, "55432"),
        ({"TEST_DATABASE_URL": "postgresql+psycopg://postgres:postgres@127.0.0.1:55432/not_test"}, "food_agent_test"),
    ],
    ids=["same-target", "sqlite", "non-psycopg", "non-loopback", "wrong-port", "wrong-database"],
)
def test_run_pg_rejects_unsafe_contract_before_running_child(
    tmp_path: Path, overrides: dict[str, str], reason: str
) -> None:
    env_file = _write_test_environment(tmp_path / ".env.test", **overrides)

    result = _run_pg(env_file, "raise SystemExit('child must not execute')")

    assert result.returncode != 0
    assert "child must not execute" not in result.stderr
    assert reason in result.stderr
    assert "postgres:postgres" not in result.stderr


def test_run_pg_preserves_distinct_urls_and_validates_in_the_child(tmp_path: Path) -> None:
    env_file = _write_test_environment(tmp_path / ".env.test")
    child = """
import os
from app.core.config import Settings, validate_test_database_configuration

settings = Settings(_env_file=None)
assert settings.app_env == 'test'
assert settings.database_url == 'postgresql+psycopg://postgres:postgres@127.0.0.1:5432/food_agent_dev'
assert settings.test_database_url == 'postgresql+psycopg://postgres:postgres@127.0.0.1:55432/food_agent_test'
assert settings.database_url != settings.test_database_url
assert validate_test_database_configuration(settings) == settings.test_database_url
print('child-contract-ok')
"""

    result = _run_pg(env_file, child)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "child-contract-ok"


def settings_for_test(**overrides: str | None) -> Settings:
    values: dict[str, str | None] = {
        "app_env": "test",
        "database_url": DEV_URL,
        "test_database_url": TEST_URL,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"test_database_url": None}, "TEST_DATABASE_URL is required"),
        (
            {"test_database_url": "sqlite+pysqlite:///:memory:"},
            "must not use SQLite",
        ),
        (
            {"test_database_url": "postgresql://postgres:postgres@localhost:5432/food_calories_test"},
            r"must use the postgresql\+psycopg dialect",
        ),
        (
            {"test_database_url": "postgresql+psycopg://postgres:postgres@localhost:5432/food_calories_dev"},
            "database name must end with '_test'",
        ),
        ({"app_env": "local"}, "APP_ENV must be 'test'"),
        ({"database_url": TEST_URL}, "must not equal TEST_DATABASE_URL"),
    ],
    ids=[
        "missing-test-url",
        "sqlite-url",
        "non-psycopg-url",
        "non-test-database-name",
        "non-test-app-env",
        "same-normalized-urls",
    ],
)
def test_unsafe_test_database_configuration_is_rejected(
    overrides: dict[str, str | None], reason: str
) -> None:
    with pytest.raises(ConfigurationError, match=reason):
        validate_test_database_configuration(settings_for_test(**overrides))


def test_valid_test_database_configuration_returns_isolated_url() -> None:
    assert validate_test_database_configuration(settings_for_test()) == TEST_URL


def production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "production",
        "database_url": "postgresql+psycopg://app:password@db:5432/food_agent",
        "test_database_url": TEST_URL,
        "secret_key": "a-production-secret-with-at-least-32-characters",
        "cookie_secure": True,
        "cors_origins": ["https://food.example.com"],
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "smtp_from_email": "noreply@example.com",
        "smtp_username": "mailer",
        "smtp_password": "provider-credential",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"database_url": "sqlite+pysqlite:///app.db"}, "DATABASE_URL must use"),
        ({"secret_key": "short"}, "SECRET_KEY"),
        ({"cookie_secure": False}, "Secure cookie"),
        ({"cors_origins": ["*"]}, "wildcard CORS"),
        ({"smtp_host": "mailpit"}, "local Mailpit"),
        ({"smtp_host": "localhost"}, "local Mailpit"),
        ({"smtp_from_email": None}, "SMTP_FROM_EMAIL"),
        ({"smtp_username": None}, "SMTP_USERNAME"),
        ({"smtp_password": None}, "SMTP_PASSWORD"),
    ],
)
def test_unsafe_production_configuration_is_rejected(
    overrides: dict[str, object], reason: str
) -> None:
    with pytest.raises((ConfigurationError, ValidationError), match=reason):
        production_settings(**overrides)


def test_local_mailpit_requires_no_cloud_credentials() -> None:
    settings = Settings(
        app_env="local",
        database_url=DEV_URL,
        test_database_url=TEST_URL,
        secret_key="local-only",
        cookie_secure=False,
        cors_origins=["http://localhost:5173"],
        smtp_host="mailpit",
        smtp_port=1025,
        smtp_from_email="noreply@local.test",
        smtp_username=None,
        smtp_password=None,
        _env_file=None,
    )

    assert settings.smtp_host == "mailpit"
    assert settings.smtp_username is None
    assert settings.smtp_password is None
