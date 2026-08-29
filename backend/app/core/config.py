"""Validated runtime settings and fail-closed environment boundaries."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal, TypeAlias

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


class ConfigurationError(ValueError):
    """Raised when runtime configuration crosses a security boundary."""


ReasoningProviderMode: TypeAlias = Literal["fake", "deepseek"]


class Settings(BaseSettings):
    """Settings loaded from environment variables or an optional backend `.env` file."""

    app_env: Literal["local", "test", "production"] = "local"
    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/food_agent_dev"
    )
    test_database_url: str | None = None
    secret_key: SecretStr = SecretStr("local-development-secret-not-for-production")
    cookie_secure: bool = False
    cors_origins: list[str] = ["http://localhost:5173"]
    smtp_host: str = "mailpit"
    smtp_port: int = 1025
    smtp_from_email: str | None = "noreply@local.test"
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    reasoning_provider_mode: ReasoningProviderMode = "fake"
    deepseek_api_key: SecretStr | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_runtime_boundaries(self) -> Settings:
        database = _url(self.database_url, variable="DATABASE_URL")
        if database.drivername != "postgresql+psycopg":
            raise ConfigurationError(
                "DATABASE_URL must use the postgresql+psycopg dialect; SQLite is forbidden"
            )

        if not self.cors_origins or "*" in self.cors_origins:
            raise ConfigurationError("wildcard CORS origins are forbidden")

        if self.app_env != "production":
            return self

        secret = self.secret_key.get_secret_value()
        if len(secret) < 32 or "local-development" in secret or "change-me" in secret:
            raise ConfigurationError("SECRET_KEY must be a strong production secret")
        if not self.cookie_secure:
            raise ConfigurationError("production requires a Secure cookie")

        local_hosts = {"mailpit", "localhost", "127.0.0.1", "::1"}
        if self.smtp_host.strip().lower() in local_hosts:
            raise ConfigurationError("production must not use local Mailpit")
        if not self.smtp_from_email:
            raise ConfigurationError("SMTP_FROM_EMAIL is required in production")
        if not self.smtp_username:
            raise ConfigurationError("SMTP_USERNAME is required in production")
        if self.smtp_password is None or not self.smtp_password.get_secret_value():
            raise ConfigurationError("SMTP_PASSWORD is required in production")
        if self.reasoning_provider_mode != "deepseek":
            raise ConfigurationError(
                "production requires REASONING_PROVIDER_MODE=deepseek"
            )
        if self.deepseek_api_key is None or not self.deepseek_api_key.get_secret_value():
            raise ConfigurationError("DEEPSEEK_API_KEY is required in production")

        return self


def _url(value: str, *, variable: str) -> URL:
    try:
        return make_url(value)
    except Exception as error:  # SQLAlchemy normalizes URL parsing for us.
        raise ConfigurationError(f"{variable} must be a valid SQLAlchemy URL") from error


def normalize_database_url(value: str) -> str:
    """Render a URL in a stable form before comparing database targets."""

    return _url(value, variable="database URL").render_as_string(hide_password=False)


def validate_test_database_configuration(settings: Settings) -> str:
    """Return the isolated test URL or raise a reason-specific configuration error.

    Test code must opt into `APP_ENV=test`, use the Psycopg PostgreSQL dialect, and
    target a database named with `_test`.  These checks intentionally reject rather
    than fall back to the application database or SQLite.
    """

    if settings.app_env != "test":
        raise ConfigurationError("APP_ENV must be 'test' when running database tests")

    if not settings.test_database_url:
        raise ConfigurationError("TEST_DATABASE_URL is required when running database tests")

    test_url = _url(settings.test_database_url, variable="TEST_DATABASE_URL")
    if test_url.drivername.startswith("sqlite"):
        raise ConfigurationError("TEST_DATABASE_URL must not use SQLite")
    if test_url.drivername != "postgresql+psycopg":
        raise ConfigurationError("TEST_DATABASE_URL must use the postgresql+psycopg dialect")
    if not test_url.database or not test_url.database.endswith("_test"):
        raise ConfigurationError("TEST_DATABASE_URL database name must end with '_test'")

    if normalize_database_url(settings.database_url) == normalize_database_url(
        settings.test_database_url
    ):
        raise ConfigurationError("DATABASE_URL must not equal TEST_DATABASE_URL during tests")

    return normalize_database_url(settings.test_database_url)


def runtime_database_url(settings: Settings) -> str:
    """Select the already-validated isolated target only for an explicit test runtime.

    This preserves DATABASE_URL as a development sentinel while ensuring all FastAPI modules
    (authentication and Agent alike) share one real, disposable PostgreSQL database in tests.
    """

    if settings.app_env == "test":
        return validate_test_database_configuration(settings)
    return settings.database_url


@lru_cache
def get_settings() -> Settings:
    """Load and cache settings only after all environment guards pass."""

    return Settings()
