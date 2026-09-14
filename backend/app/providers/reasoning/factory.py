"""Provider selection with test isolation and production fail-closed behaviour."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Literal

from app.core.config import ConfigurationError, ReasoningProviderMode, Settings
from app.core.tracing import TracingRuntime
from app.providers.reasoning.deepseek import DeepSeekReasoningModelProvider
from app.providers.reasoning.fake import RiceOnlyFakeReasoningModelProvider
from app.providers.reasoning.ports import ReasoningModelProvider


def create_reasoning_provider(
    settings: Settings | None = None,
    *,
    app_env: Literal["local", "test", "production"] | None = None,
    provider_mode: ReasoningProviderMode | None = None,
    runtime_config: Mapping[str, object] | None = None,
    tracing: TracingRuntime | None = None,
) -> ReasoningModelProvider:
    """Select only a configured adapter; test never reaches a paid network provider."""

    if settings is not None and (app_env is not None or provider_mode is not None):
        raise TypeError("Pass either settings or explicit provider selection, not both")
    if settings is not None:
        app_env = settings.app_env
        provider_mode = settings.reasoning_provider_mode

    if runtime_config is not None:
        allowed = {"provider", "model_alias", "enabled", "single_call_cap_usd", "period_cap_usd", "input_usd_per_m", "output_usd_per_m", "version"}
        if set(runtime_config) != allowed or not runtime_config.get("enabled", False):
            raise ConfigurationError("runtime config is invalid or disabled")
        if runtime_config["provider"] != "deepseek" or runtime_config["model_alias"] != "deepseek-v4-flash":
            raise ConfigurationError("runtime config provider or model is unsupported")

    if app_env is None:
        raise ConfigurationError("APP_ENV is required to choose a reasoning provider")
    if app_env == "test":
        return RiceOnlyFakeReasoningModelProvider()
    if provider_mode is None:
        raise ConfigurationError("REASONING_PROVIDER_MODE must be explicitly configured")
    if app_env == "production" and provider_mode != "deepseek":
        raise ConfigurationError("production requires REASONING_PROVIDER_MODE=deepseek")
    if provider_mode == "fake":
        return RiceOnlyFakeReasoningModelProvider()
    if provider_mode == "deepseek":
        if settings is None:
            raise ConfigurationError("DeepSeek provider requires Settings")
        if settings.deepseek_api_key is None or not settings.deepseek_api_key.get_secret_value():
            raise ConfigurationError("DEEPSEEK_API_KEY is required for the DeepSeek provider")
        configured_model = runtime_config["model_alias"] if runtime_config is not None else settings.deepseek_model
        if not configured_model:
            raise ConfigurationError("DEEPSEEK_MODEL is required for the DeepSeek provider")
        if not settings.deepseek_price_snapshot_version:
            raise ConfigurationError(
                "DEEPSEEK_PRICE_SNAPSHOT_VERSION is required for the DeepSeek provider"
            )
        try:
            input_price = Decimal(str(runtime_config["input_usd_per_m"])) if runtime_config is not None else settings.deepseek_input_usd_per_m
            output_price = Decimal(str(runtime_config["output_usd_per_m"])) if runtime_config is not None else settings.deepseek_output_usd_per_m
        except (InvalidOperation, ValueError) as error:
            raise ConfigurationError("runtime config prices must be decimals") from error
        if input_price is None or output_price is None or input_price < 0 or output_price < 0:
            raise ConfigurationError(
                "DEEPSEEK_INPUT_USD_PER_M and DEEPSEEK_OUTPUT_USD_PER_M are required"
            )
        return DeepSeekReasoningModelProvider(
            api_key=settings.deepseek_api_key.get_secret_value(),
            model=str(configured_model),
            timeout_seconds=20,
            price_snapshot={
                "input_usd_per_m": input_price,
                "output_usd_per_m": output_price,
            },
            tracing=tracing,
        )
    raise ConfigurationError("unsupported reasoning provider mode")
