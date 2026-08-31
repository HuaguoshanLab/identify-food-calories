"""Contract tests for the isolated reasoning-model provider boundary."""

from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.core.config import ConfigurationError, Settings
from app.providers.reasoning.dto import (
    ApplyCorrectionRequest,
    ParseMealRequest,
    ParsedMealDTO,
    ParsedMealItemDTO,
    ProviderCallError,
    ProviderFailureKind,
    ProviderUsageDTO,
)
from app.providers.reasoning.factory import create_reasoning_provider
from app.providers.reasoning.deepseek import DeepSeekReasoningModelProvider
from app.providers.reasoning.fake import FakeReasoningModelProvider


def test_test_environment_always_uses_the_fake_provider() -> None:
    provider = create_reasoning_provider(app_env="test", provider_mode="deepseek")

    assert isinstance(provider, FakeReasoningModelProvider)


def test_production_requires_an_explicit_deepseek_provider_configuration() -> None:
    with pytest.raises((ConfigurationError, ValidationError), match="REASONING_PROVIDER_MODE"):
        Settings(
            _env_file=None,
            app_env="production",
            secret_key="a-strong-production-secret-value-that-is-long-enough",
            cookie_secure=True,
            cors_origins=["https://app.example.com"],
            smtp_host="smtp.example.com",
            smtp_from_email="noreply@example.com",
            smtp_username="mailer",
            smtp_password="password",
        )


def test_deepseek_provider_requires_complete_runtime_configuration() -> None:
    with pytest.raises(ConfigurationError, match="requires Settings"):
        create_reasoning_provider(app_env="production", provider_mode="deepseek")

    with pytest.raises(ConfigurationError, match="DEEPSEEK_API_KEY"):
        create_reasoning_provider(
            Settings(app_env="local", reasoning_provider_mode="deepseek", _env_file=None)
        )


def test_deepseek_provider_is_selected_from_local_settings() -> None:
    provider = create_reasoning_provider(
        Settings(
            app_env="local",
            reasoning_provider_mode="deepseek",
            deepseek_api_key="test-key",
            deepseek_model="deepseek-v4-flash",
            deepseek_price_snapshot_version="price-v1",
            deepseek_input_usd_per_m="1",
            deepseek_output_usd_per_m="2",
            _env_file=None,
        )
    )

    assert isinstance(provider, DeepSeekReasoningModelProvider)


def test_fake_scripts_safe_results_and_preserves_no_raw_request_text_in_trace() -> None:
    provider = FakeReasoningModelProvider()
    provider.queue_parse_result(
        ParsedMealDTO(
            items=[
                ParsedMealItemDTO(
                    item_id="rice",
                    food_name="cooked rice",
                    quantity_text="150 g",
                    grams=150,
                )
            ]
        ),
        usage=ProviderUsageDTO(
            prompt_tokens=12,
            completion_tokens=8,
            cost_usd="0.0012",
        ),
        latency_ms=31,
    )

    result = asyncio.run(
        provider.parse_meal(ParseMealRequest(meal_description="敏感的原始餐食描述"))
    )

    assert result.value.items[0].food_name == "cooked rice"
    assert result.metadata.usage.total_tokens == 20
    assert result.metadata.usage.cost_usd == Decimal("0.0012")
    assert result.metadata.latency_ms == 31
    assert provider.calls[0].operation == "parse_meal"
    assert "敏感" not in repr(provider.calls[0])


@pytest.mark.parametrize(
    "kind",
    [
        ProviderFailureKind.TRANSIENT,
        ProviderFailureKind.PERMANENT,
        ProviderFailureKind.OUTCOME_UNKNOWN,
    ],
)
def test_fake_can_script_each_safe_failure_kind(kind: ProviderFailureKind) -> None:
    provider = FakeReasoningModelProvider()
    provider.queue_correction_error(kind=kind, code="safe_code")

    with pytest.raises(ProviderCallError) as error:
        asyncio.run(
            provider.apply_correction(
                ApplyCorrectionRequest(correction_text="不要记录这个原始内容")
            )
        )

    assert error.value.kind is kind
    assert error.value.code == "safe_code"
    assert provider.calls[0].operation == "apply_correction"
    assert "原始内容" not in repr(provider.calls[0])
