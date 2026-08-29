"""Provider selection with test isolation and production fail-closed behaviour."""

from __future__ import annotations

from typing import Literal

from app.core.config import ConfigurationError, ReasoningProviderMode, Settings
from app.providers.reasoning.fake import FakeReasoningModelProvider
from app.providers.reasoning.ports import ReasoningModelProvider


def create_reasoning_provider(
    settings: Settings | None = None,
    *,
    app_env: Literal["local", "test", "production"] | None = None,
    provider_mode: ReasoningProviderMode | None = None,
) -> ReasoningModelProvider:
    """Select only a configured adapter; test never reaches a paid network provider."""

    if settings is not None and (app_env is not None or provider_mode is not None):
        raise TypeError("Pass either settings or explicit provider selection, not both")
    if settings is not None:
        app_env = settings.app_env
        provider_mode = settings.reasoning_provider_mode

    if app_env is None:
        raise ConfigurationError("APP_ENV is required to choose a reasoning provider")
    if app_env == "test":
        return FakeReasoningModelProvider()
    if provider_mode is None:
        raise ConfigurationError("REASONING_PROVIDER_MODE must be explicitly configured")
    if app_env == "production" and provider_mode != "deepseek":
        raise ConfigurationError("production requires REASONING_PROVIDER_MODE=deepseek")
    if provider_mode == "fake":
        return FakeReasoningModelProvider()
    if provider_mode == "deepseek":
        raise ConfigurationError(
            "DeepSeek reasoning adapter is not installed; production startup is blocked"
        )
    raise ConfigurationError("unsupported reasoning provider mode")
