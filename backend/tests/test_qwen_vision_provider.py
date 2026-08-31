"""Transport-only tests for Qwen-VL's retry, structure and accounting boundary."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.images.schemas import ValidatedImageReference
from app.providers.reasoning.dto import ProviderCallError, ProviderFailureKind
from app.providers.vision.dto import VisionMealRequest
from app.providers.vision.qwen import MIN_PIXELS, VISION_JSON_CONTRACT, QwenPriceTier, QwenVisionModelProvider


def _request() -> VisionMealRequest:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return VisionMealRequest(
        image=ValidatedImageReference(digest_sha256="a" * 64, mime_type="image/jpeg", width=12, height=8, byte_size=12, locator="b" * 32 + ".jpg", created_at=now, expires_at=now + timedelta(minutes=5)),
        model_alias="qwen-vl-test", pixel_budget=100_000, request_key="safe-request-key",
    )


def _provider(transport: httpx.AsyncBaseTransport) -> QwenVisionModelProvider:
    return QwenVisionModelProvider(
        api_key="secret-key", model="qwen-vl-test", endpoint="https://qwen.example/v1/chat/completions",
        timeout_seconds=20, max_pixels=20_000_000, price_tiers=(QwenPriceTier(32_000, "0.15", "1.5"), QwenPriceTier(128_000, "0.3", "3"), QwenPriceTier(256_000, "0.6", "6")),
        image_loader=lambda reference: b"normalized-image-bytes", transport=transport,
    )


def _success(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, request=request, headers={"x-request-id": "provider-request"}, json={
        "id": "ignored-id", "choices": [{"message": {"content": json.dumps({"items": [{"item_id": "rice", "food_name": "米饭", "estimated_grams": "120", "confidence": "0.8"}]})}}],
        "usage": {"prompt_tokens": 20, "completion_tokens": 5, "prompt_tokens_details": {"image_tokens": 7}},
    })


def test_qwen_request_is_non_thinking_json_and_retries_one_safe_transient_response() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(429, request=request, json={"error": {"message": "hidden"}})
        return _success(request)

    result = asyncio.run(_provider(httpx.MockTransport(handler)).analyze_meal_image(_request()))

    assert len(requests) == 2
    sent = json.loads(requests[-1].content)
    assert sent["enable_thinking"] is False
    assert sent["response_format"] == {"type": "json_object"}
    assert sent["messages"][0]["content"][1]["text"] == VISION_JSON_CONTRACT
    assert '"estimated_grams":number or null' in sent["messages"][0]["content"][1]["text"]
    assert sent["messages"][0]["content"][0]["image_url"]["min_pixels"] == MIN_PIXELS
    assert sent["messages"][0]["content"][0]["image_url"]["max_pixels"] == 100_000
    assert sent["messages"][0]["content"][0]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert requests[-1].headers["x-request-id"] == "safe-request-key"
    assert result.metadata.provider_request_id == "provider-request"
    assert result.metadata.usage.image_tokens == 7
    assert result.metadata.usage.prompt_tokens == 13
    assert str(result.metadata.usage.cost_cny) == "0.0000105"


@pytest.mark.parametrize(
    "response_factory",
    [
        lambda request: httpx.Response(200, request=request, json={"choices": [{"message": {"content": "{}"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}}),
        lambda request: httpx.Response(200, request=request, json={"choices": [{"message": {"content": '{"items":[{"item_id":"x","food_name":"x","confidence":"1","unexpected":true}]}'}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}}),
    ],
)
def test_qwen_rejects_invalid_json_or_schema_without_exposing_response(response_factory: object) -> None:
    provider = _provider(httpx.MockTransport(response_factory))

    with pytest.raises(ProviderCallError) as error:
        asyncio.run(provider.analyze_meal_image(_request()))

    assert error.value.kind is ProviderFailureKind.PERMANENT
    assert error.value.code == "PROVIDER_SCHEMA_INVALID"


def test_qwen_rejects_permanent_http_errors_and_never_retries_unknown_transport_outcome() -> None:
    calls = 0

    def timeout(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("unknown", request=request)

    with pytest.raises(ProviderCallError) as unknown:
        asyncio.run(_provider(httpx.MockTransport(timeout)).analyze_meal_image(_request()))
    assert unknown.value.kind is ProviderFailureKind.OUTCOME_UNKNOWN
    assert calls == 1

    with pytest.raises(ProviderCallError) as rejected:
        asyncio.run(_provider(httpx.MockTransport(lambda request: httpx.Response(400, request=request))).analyze_meal_image(_request()))
    assert rejected.value.kind is ProviderFailureKind.PERMANENT
    assert rejected.value.code == "PROVIDER_REQUEST_REJECTED"
