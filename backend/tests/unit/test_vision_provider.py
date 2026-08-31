"""Contract tests for the image-safe, independently typed Vision Provider boundary."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import ConfigurationError, Settings
from app.images.schemas import ValidatedImageReference
from app.providers.reasoning.dto import ProviderCallError, ProviderFailureKind
from app.providers.vision.dto import VisionMealItemDTO, VisionMealRequest, VisionUsageDTO
from app.providers.vision.factory import create_vision_provider
from app.providers.vision.fake import FakeVisionModelProvider


def _request() -> VisionMealRequest:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return VisionMealRequest(
        image=ValidatedImageReference(
            digest_sha256="a" * 64, mime_type="image/jpeg", width=12, height=8, byte_size=100,
            locator="b" * 32 + ".jpg", created_at=now, expires_at=now + timedelta(minutes=5),
        ),
        model_alias="fake-vision-v1", pixel_budget=1000,
    )


def test_test_environment_always_uses_fake_vision_provider() -> None:
    assert isinstance(create_vision_provider(app_env="test", provider_mode="qwen"), FakeVisionModelProvider)


def test_fake_scripts_success_and_safe_failure_categories_without_retaining_image_reference() -> None:
    provider = FakeVisionModelProvider()
    provider.queue_result(
        [VisionMealItemDTO(item_id="rice", food_name="米饭", estimated_grams="100", confidence="0.9")],
        usage=VisionUsageDTO(image_tokens=12, prompt_tokens=3, completion_tokens=4, cost_cny="0.001"),
    )
    result = asyncio.run(provider.analyze_meal_image(_request()))

    assert result.items[0].estimated_grams == 100
    assert result.metadata.usage.total_tokens == 19
    assert provider.calls[0].image_tokens == 12
    assert "digest" not in repr(provider.calls[0])

    for kind in ProviderFailureKind:
        provider.queue_error(kind=kind, code=f"{kind.value}-safe")
        with pytest.raises(ProviderCallError) as error:
            asyncio.run(provider.analyze_meal_image(_request()))
        assert error.value.kind is kind

    provider.queue_schema_invalid()
    with pytest.raises(ProviderCallError) as schema_error:
        asyncio.run(provider.analyze_meal_image(_request()))
    assert schema_error.value.code == "PROVIDER_SCHEMA_INVALID"


def test_factory_refuses_unconfigured_qwen_instead_of_falling_back() -> None:
    with pytest.raises(ConfigurationError, match="requires Settings"):
        create_vision_provider(app_env="production", provider_mode="qwen")
    with pytest.raises(ConfigurationError, match="Qwen provider requires"):
        create_vision_provider(Settings(app_env="local", vision_provider_mode="qwen", _env_file=None))
