"""Embedding-provider selection keeps tests offline and production fail closed."""

from __future__ import annotations

from importlib import import_module
from typing import Literal

from app.core.config import ConfigurationError, EmbeddingProviderMode, Settings
from app.providers.embedding.fake import FakeEmbeddingProvider
from app.providers.embedding.ports import EmbeddingProvider


def create_embedding_provider(
    settings: Settings | None = None,
    *,
    app_env: Literal["local", "test", "production"] | None = None,
    provider_mode: EmbeddingProviderMode | None = None,
) -> EmbeddingProvider | None:
    """Construct a provider from trusted configuration; test cannot reach DashScope."""

    if settings is not None and (app_env is not None or provider_mode is not None):
        raise TypeError("Pass either settings or explicit provider selection, not both")
    if settings is not None:
        app_env = settings.app_env
        provider_mode = settings.embedding_provider_mode
    if app_env is None:
        raise ConfigurationError("APP_ENV is required to choose an embedding provider")
    if app_env == "test":
        return FakeEmbeddingProvider()
    if provider_mode is None:
        raise ConfigurationError("EMBEDDING_PROVIDER_MODE must be explicitly configured")
    if app_env == "production" and provider_mode != "dashscope":
        raise ConfigurationError("production requires EMBEDDING_PROVIDER_MODE=dashscope")
    if provider_mode == "disabled":
        return None
    if provider_mode == "fake":
        return FakeEmbeddingProvider()
    if provider_mode != "dashscope" or settings is None:
        raise ConfigurationError("DashScope embedding provider requires Settings")
    if settings.dashscope_api_key is None or not settings.dashscope_api_key.get_secret_value().strip():
        raise ConfigurationError("DASHSCOPE_API_KEY is required for the DashScope embedding provider")
    try:
        adapter_module = import_module("app.providers.embedding.dashscope")
        adapter_class = getattr(adapter_module, "DashScopeEmbeddingProvider")
        return adapter_class.from_settings(settings)
    except (ImportError, AttributeError, ValueError) as error:
        raise ConfigurationError("DashScope embedding provider configuration is invalid") from error
