"""Vision provider selection keeps tests offline and production fail-closed."""

from __future__ import annotations

from importlib import import_module
from typing import Literal

from app.core.config import ConfigurationError, Settings, VisionProviderMode
from app.providers.vision.fake import FakeVisionModelProvider
from app.providers.vision.ports import VisionModelProvider


def create_vision_provider(
    settings: Settings | None = None,
    *,
    app_env: Literal["local", "test", "production"] | None = None,
    provider_mode: VisionProviderMode | None = None,
) -> VisionModelProvider:
    """Select a configured adapter; test cannot cross the paid-provider boundary."""

    if settings is not None and (app_env is not None or provider_mode is not None):
        raise TypeError("Pass either settings or explicit provider selection, not both")
    if settings is not None:
        app_env = settings.app_env
        provider_mode = settings.vision_provider_mode
    if app_env is None:
        raise ConfigurationError("APP_ENV is required to choose a vision provider")
    if app_env == "test":
        return FakeVisionModelProvider()
    if provider_mode is None:
        raise ConfigurationError("VISION_PROVIDER_MODE must be explicitly configured")
    if app_env == "production" and provider_mode != "qwen":
        raise ConfigurationError("production requires VISION_PROVIDER_MODE=qwen")
    if provider_mode == "fake":
        return FakeVisionModelProvider()
    if settings is None:
        raise ConfigurationError("Qwen vision provider requires Settings")
    if (
        settings.qwen_api_key is None
        or not settings.qwen_api_key.get_secret_value().strip()
        or not settings.qwen_model
        or not settings.qwen_region
        or not settings.qwen_deployment_scope
        or not settings.qwen_base_url
    ):
        raise ConfigurationError("Qwen provider requires API key, model, region and deployment scope")
    try:
        adapter_module = import_module("app.providers.vision.qwen")
        adapter_class = getattr(adapter_module, "QwenVisionModelProvider")
    except ImportError as error:
        raise ConfigurationError("Qwen vision provider adapter is unavailable") from error
    return adapter_class.from_settings(settings)
