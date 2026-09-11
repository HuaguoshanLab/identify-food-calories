"""Validated runtime settings and fail-closed environment boundaries."""

from __future__ import annotations

from functools import lru_cache
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal, TypeAlias

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


class ConfigurationError(ValueError):
    """Raised when runtime configuration crosses a security boundary."""


ReasoningProviderMode: TypeAlias = Literal["fake", "deepseek"]
VisionProviderMode: TypeAlias = Literal["fake", "qwen"]
MemoryProviderMode: TypeAlias = Literal["fake", "mem0"]
EmbeddingProviderMode: TypeAlias = Literal["disabled", "fake", "dashscope"]


class Settings(BaseSettings):
    """Settings loaded from environment variables or an optional backend `.env` file."""

    app_env: Literal["local", "test", "production"] = "local"
    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/food_agent_dev"
    )
    test_database_url: str | None = None
    secret_key: SecretStr = SecretStr("local-development-secret-not-for-production")
    cookie_secure: bool = False
    # Also used by the refresh/logout CSRF gate: configure both user and admin
    # browser origins explicitly, even when their requests use a Vite proxy.
    cors_origins: list[str] = ["http://localhost:5173"]
    smtp_host: str = "mailpit"
    smtp_port: int = 1025
    smtp_from_email: str | None = "noreply@local.test"
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    # Deliberately local-only: the password comes from the ignored .env file, never source.
    local_bootstrap_admin_password: SecretStr | None = None
    reasoning_provider_mode: ReasoningProviderMode = "fake"
    deepseek_api_key: SecretStr | None = None
    deepseek_model: str | None = None
    deepseek_price_snapshot_version: str | None = None
    deepseek_input_usd_per_m: Decimal | None = None
    deepseek_output_usd_per_m: Decimal | None = None
    tracing_enabled: bool = False
    tracing_collector_endpoint: str | None = None
    tracing_hmac_key: SecretStr | None = None
    tracing_service_name: str | None = None
    tracing_service_version: str | None = None
    retention_checkpoint_event_days: int = 7
    retention_audit_days: int = 30
    retention_deletion_sla_hours: int = 24
    retention_poll_interval_seconds: int = 300
    image_max_bytes: int = 10 * 1024 * 1024
    image_max_pixels: int = 20_000_000
    image_temporary_directory: Path = Path("/tmp/food-agent-images")
    image_ttl_seconds: int = 300
    vision_provider_mode: VisionProviderMode = "fake"
    qwen_api_key: SecretStr | None = None
    qwen_model: str | None = None
    qwen_region: str | None = None
    qwen_deployment_scope: str | None = None
    qwen_base_url: str | None = None
    qwen_price_snapshot_version: str | None = None
    qwen_up_to_32k_input_cny_per_m: Decimal | None = None
    qwen_up_to_32k_output_cny_per_m: Decimal | None = None
    qwen_up_to_128k_input_cny_per_m: Decimal | None = None
    qwen_up_to_128k_output_cny_per_m: Decimal | None = None
    qwen_up_to_256k_input_cny_per_m: Decimal | None = None
    qwen_up_to_256k_output_cny_per_m: Decimal | None = None
    vision_timeout_seconds: int = 20
    vision_max_pixels: int = 20_000_000
    memory_provider_mode: MemoryProviderMode = "fake"
    mem0_api_key: SecretStr | None = None
    mem0_endpoint: str | None = None
    memory_operation_timeout_seconds: int = 10
    memory_retry_max_attempts: int = 3
    memory_retry_backoff_seconds: int = 30
    embedding_provider_mode: EmbeddingProviderMode = "fake"
    dashscope_api_key: SecretStr | None = None
    embedding_model: str | None = None
    embedding_dimension: int | None = None
    embedding_adapter_version: str | None = None
    embedding_price_snapshot_version: str | None = None
    embedding_input_cny_per_m: Decimal | None = None
    embedding_single_call_cap_cny: Decimal | None = None
    embedding_period_cap_cny: Decimal | None = None
    embedding_timeout_seconds: float | None = None

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

        retention_values = {
            "RETENTION_CHECKPOINT_EVENT_DAYS": self.retention_checkpoint_event_days,
            "RETENTION_AUDIT_DAYS": self.retention_audit_days,
            "RETENTION_DELETION_SLA_HOURS": self.retention_deletion_sla_hours,
            "RETENTION_POLL_INTERVAL_SECONDS": self.retention_poll_interval_seconds,
        }
        for variable, value in retention_values.items():
            if value is not None and value <= 0:
                raise ConfigurationError(f"{variable} must be positive when configured")
        if self.retention_poll_interval_seconds is not None and self.retention_poll_interval_seconds > 300:
            raise ConfigurationError("RETENTION_POLL_INTERVAL_SECONDS must not exceed 300")

        if self.app_env != "production":
            return self

        if (
            self.local_bootstrap_admin_password is not None
            and self.local_bootstrap_admin_password.get_secret_value()
        ):
            raise ConfigurationError("LOCAL_BOOTSTRAP_ADMIN_PASSWORD is only allowed locally")

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
        if not self.deepseek_model:
            raise ConfigurationError("DEEPSEEK_MODEL is required in production")
        if not self.deepseek_price_snapshot_version:
            raise ConfigurationError(
                "DEEPSEEK_PRICE_SNAPSHOT_VERSION is required in production"
            )
        prices = (self.deepseek_input_usd_per_m, self.deepseek_output_usd_per_m)
        if any(price is None or price < 0 for price in prices):
            raise ConfigurationError(
                "DEEPSEEK_INPUT_USD_PER_M and DEEPSEEK_OUTPUT_USD_PER_M are required"
            )
        if self.tracing_enabled:
            if not self.tracing_collector_endpoint:
                raise ConfigurationError(
                    "TRACING_COLLECTOR_ENDPOINT is required when tracing is enabled"
                )
            if self.tracing_hmac_key is None or not self.tracing_hmac_key.get_secret_value():
                raise ConfigurationError("TRACING_HMAC_KEY is required when tracing is enabled")
            if not self.tracing_service_name:
                raise ConfigurationError(
                    "TRACING_SERVICE_NAME is required when tracing is enabled"
                )
            if not self.tracing_service_version:
                raise ConfigurationError(
                    "TRACING_SERVICE_VERSION is required when tracing is enabled"
                )

        for variable, value in retention_values.items():
            if value is None or value <= 0:
                raise ConfigurationError(f"{variable} must be explicitly positive in production")
            if variable.lower() not in self.model_fields_set:
                raise ConfigurationError(f"{variable} must be explicitly configured in production")
        if self.retention_deletion_sla_hours * 3600 <= self.retention_poll_interval_seconds:
            raise ConfigurationError("retention deletion SLA must exceed the poll interval")

        image_values = {
            "IMAGE_MAX_BYTES": self.image_max_bytes,
            "IMAGE_MAX_PIXELS": self.image_max_pixels,
            "IMAGE_TTL_SECONDS": self.image_ttl_seconds,
        }
        for variable, value in image_values.items():
            if value <= 0:
                raise ConfigurationError(f"{variable} must be positive")
            if variable.lower() not in self.model_fields_set:
                raise ConfigurationError(f"{variable} must be explicitly configured in production")
        if "image_temporary_directory" not in self.model_fields_set:
            raise ConfigurationError("IMAGE_TEMPORARY_DIRECTORY is required in production")
        if not self.image_temporary_directory.is_absolute() or self.image_temporary_directory == Path("/"):
            raise ConfigurationError("IMAGE_TEMPORARY_DIRECTORY must be a private absolute directory")
        if self.vision_provider_mode != "qwen":
            raise ConfigurationError("production requires VISION_PROVIDER_MODE=qwen")
        vision_required = {
            "QWEN_API_KEY": self.qwen_api_key.get_secret_value() if self.qwen_api_key else None,
            "QWEN_MODEL": self.qwen_model,
            "QWEN_REGION": self.qwen_region,
            "QWEN_DEPLOYMENT_SCOPE": self.qwen_deployment_scope,
            "QWEN_BASE_URL": self.qwen_base_url,
            "QWEN_PRICE_SNAPSHOT_VERSION": self.qwen_price_snapshot_version,
            "QWEN_UP_TO_32K_INPUT_CNY_PER_M": self.qwen_up_to_32k_input_cny_per_m,
            "QWEN_UP_TO_32K_OUTPUT_CNY_PER_M": self.qwen_up_to_32k_output_cny_per_m,
            "QWEN_UP_TO_128K_INPUT_CNY_PER_M": self.qwen_up_to_128k_input_cny_per_m,
            "QWEN_UP_TO_128K_OUTPUT_CNY_PER_M": self.qwen_up_to_128k_output_cny_per_m,
            "QWEN_UP_TO_256K_INPUT_CNY_PER_M": self.qwen_up_to_256k_input_cny_per_m,
            "QWEN_UP_TO_256K_OUTPUT_CNY_PER_M": self.qwen_up_to_256k_output_cny_per_m,
        }
        for variable, vision_value in vision_required.items():
            if vision_value is None or not str(vision_value).strip():
                raise ConfigurationError(f"{variable} is required in production")
        if self.vision_timeout_seconds <= 0 or self.vision_max_pixels <= 0:
            raise ConfigurationError("VISION_TIMEOUT_SECONDS and VISION_MAX_PIXELS must be positive")
        for field in ("vision_timeout_seconds", "vision_max_pixels"):
            if field not in self.model_fields_set:
                raise ConfigurationError(f"{field.upper()} must be explicitly configured in production")
        if self.memory_provider_mode != "mem0":
            raise ConfigurationError("production requires MEMORY_PROVIDER_MODE=mem0")
        memory_required = {
            "MEM0_API_KEY": self.mem0_api_key.get_secret_value() if self.mem0_api_key else None,
            "MEM0_ENDPOINT": self.mem0_endpoint,
        }
        for variable, memory_value in memory_required.items():
            if memory_value is None or not str(memory_value).strip():
                raise ConfigurationError(f"{variable} is required in production")
        if self.memory_operation_timeout_seconds <= 0 or self.memory_retry_max_attempts <= 0 or self.memory_retry_backoff_seconds <= 0:
            raise ConfigurationError("memory timeout and retry settings must be positive")
        for field in ("memory_operation_timeout_seconds", "memory_retry_max_attempts", "memory_retry_backoff_seconds"):
            if field not in self.model_fields_set:
                raise ConfigurationError(f"{field.upper()} must be explicitly configured in production")

        if self.embedding_provider_mode != "dashscope":
            raise ConfigurationError("production requires EMBEDDING_PROVIDER_MODE=dashscope")
        embedding_required = {
            "DASHSCOPE_API_KEY": self.dashscope_api_key.get_secret_value() if self.dashscope_api_key else None,
            "EMBEDDING_MODEL": self.embedding_model,
            "EMBEDDING_DIMENSION": self.embedding_dimension,
            "EMBEDDING_ADAPTER_VERSION": self.embedding_adapter_version,
            "EMBEDDING_PRICE_SNAPSHOT_VERSION": self.embedding_price_snapshot_version,
            "EMBEDDING_INPUT_CNY_PER_M": self.embedding_input_cny_per_m,
            "EMBEDDING_SINGLE_CALL_CAP_CNY": self.embedding_single_call_cap_cny,
            "EMBEDDING_PERIOD_CAP_CNY": self.embedding_period_cap_cny,
            "EMBEDDING_TIMEOUT_SECONDS": self.embedding_timeout_seconds,
        }
        for variable, embedding_value in embedding_required.items():
            if embedding_value is None or not str(embedding_value).strip():
                raise ConfigurationError(f"{variable} is required in production")
        for field in (
            "embedding_model", "embedding_dimension", "embedding_adapter_version",
            "embedding_price_snapshot_version", "embedding_input_cny_per_m",
            "embedding_single_call_cap_cny", "embedding_period_cap_cny", "embedding_timeout_seconds",
        ):
            if field not in self.model_fields_set:
                raise ConfigurationError(f"{field.upper()} must be explicitly configured in production")
        if self.embedding_model != "text-embedding-v4" or self.embedding_dimension != 1024:
            raise ConfigurationError("embedding model and dimension must be text-embedding-v4/1024")
        if self.embedding_timeout_seconds != 1.5:
            raise ConfigurationError("EMBEDDING_TIMEOUT_SECONDS must be exactly 1.5")
        if any(value is None or value <= 0 for value in (
            self.embedding_input_cny_per_m, self.embedding_single_call_cap_cny,
            self.embedding_period_cap_cny,
        )):
            raise ConfigurationError("embedding price and cost caps must be positive")

        return self

    @property
    def retention_deletion_due_delta(self) -> timedelta:
        """Latest safe claim deadline, leaving one poll interval before the 24h SLA."""

        return timedelta(hours=self.retention_deletion_sla_hours) - timedelta(
            seconds=self.retention_poll_interval_seconds
        )


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
