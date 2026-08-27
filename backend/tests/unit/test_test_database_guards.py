"""Direct evidence that unsafe database test configuration is rejected."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import ConfigurationError, Settings, validate_test_database_configuration


TEST_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/food_calories_test"
DEV_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/food_calories_dev"


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
