"""Qwen-VL HTTP adapter: transient image bytes exist only inside one outbound request."""

from __future__ import annotations
from app.core.logging import observed

import base64
import json
import logging
from dataclasses import dataclass
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from time import monotonic
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.config import Settings
from app.images.repository import PrivateTemporaryImageRepository
from app.images.schemas import ValidatedImageReference
from app.providers.reasoning.dto import ProviderCallError, ProviderFailureKind
from app.providers.vision.dto import VisionCallMetadataDTO, VisionMealRequest, VisionMealResult, VisionUsageDTO


LOGGER = logging.getLogger(__name__)
MAX_COMPLETION_TOKENS = 800
# Qwen3-VL requires 65,536 pixels as its minimum image token budget.  The
# older 3,136 value applies to earlier VL families and causes the current
# Model Studio endpoint to reject otherwise valid image requests.
MIN_PIXELS = 65_536
VISION_JSON_CONTRACT = (
    'Return JSON only, with exactly this top-level object: '
    '{"items":[{"item_id":"item-1","food_name":"string","preparation":"string or null",'
    '"portion_clue":"string or null","estimated_grams":number or null,"confidence":number}]}. '
    'For a finished mixed dish, prefer its common prepared dish name rather than splitting visible '
    'ingredients; for stir-fried pork with green or red chili peppers, use the food_name "辣椒炒肉". '
    'Only split components when they are separately served foods. item_id must be a short unique identifier. confidence must be '
    'a number from 0 to 1. estimated_grams must be a positive number in grams when visible, otherwise null. '
    'Do not include nutrition values, explanations, Markdown, or any other fields.'
)


class QwenVisionModelProvider:
    """Call Qwen's OpenAI-compatible endpoint without leaking request or model bodies."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        endpoint: str,
        timeout_seconds: int,
        max_pixels: int,
        price_tiers: tuple[QwenPriceTier, ...],
        image_loader: Callable[[ValidatedImageReference], bytes],
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key.strip() or not model.strip() or not endpoint.startswith("https://"):
            raise ValueError("Qwen requires API key, model and HTTPS endpoint")
        if timeout_seconds <= 0 or max_pixels < MIN_PIXELS:
            raise ValueError("Qwen timeout and pixel budget are invalid")
        self._api_key = api_key
        self._model = model
        self._endpoint = endpoint
        self._timeout_seconds = timeout_seconds
        self._max_pixels = max_pixels
        if not price_tiers or tuple(tier.max_input_tokens for tier in price_tiers) != tuple(sorted(tier.max_input_tokens for tier in price_tiers)):
            raise ValueError("Qwen price tiers must be non-empty and sorted")
        self._price_tiers = price_tiers
        self._image_loader = image_loader
        self._transport = transport

    @classmethod
    def from_settings(cls, settings: Settings) -> QwenVisionModelProvider:
        if settings.qwen_api_key is None or not settings.qwen_model or not settings.qwen_base_url:
            raise ValueError("Qwen Settings are incomplete")
        repository = PrivateTemporaryImageRepository(settings.image_temporary_directory)
        return cls(
            api_key=settings.qwen_api_key.get_secret_value(),
            model=settings.qwen_model,
            endpoint=settings.qwen_base_url.rstrip("/") + "/chat/completions",
            timeout_seconds=settings.vision_timeout_seconds,
            max_pixels=settings.vision_max_pixels,
            price_tiers=(
                QwenPriceTier(32_000, settings.qwen_up_to_32k_input_cny_per_m or Decimal("0"), settings.qwen_up_to_32k_output_cny_per_m or Decimal("0")),
                QwenPriceTier(128_000, settings.qwen_up_to_128k_input_cny_per_m or Decimal("0"), settings.qwen_up_to_128k_output_cny_per_m or Decimal("0")),
                QwenPriceTier(256_000, settings.qwen_up_to_256k_input_cny_per_m or Decimal("0"), settings.qwen_up_to_256k_output_cny_per_m or Decimal("0")),
            ),
            image_loader=lambda reference: repository.read_path(reference).read_bytes(),
        )

    @observed("provider")
    async def analyze_meal_image(self, request: VisionMealRequest) -> VisionMealResult:
        if request.pixel_budget > self._max_pixels:
            raise ProviderCallError(kind=ProviderFailureKind.PERMANENT, code="VISION_PIXEL_BUDGET_EXCEEDED")
        try:
            body = self._body(request)
        except ProviderCallError:
            raise
        except (FileNotFoundError, OSError, ValueError) as error:
            raise ProviderCallError(
                kind=ProviderFailureKind.PERMANENT,
                code="VALIDATED_IMAGE_UNAVAILABLE",
            ) from error
        started = monotonic()
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(self._timeout_seconds), transport=self._transport) as client:
                    response = await client.post(
                        self._endpoint,
                        headers={"Authorization": f"Bearer {self._api_key}", "X-Request-Id": request.request_key},
                        json=body,
                    )
            except (httpx.TimeoutException, httpx.NetworkError, httpx.ProtocolError) as error:
                # A transport loss is ambiguous: retrying could duplicate billed inference.
                raise ProviderCallError(kind=ProviderFailureKind.OUTCOME_UNKNOWN, code="PROVIDER_OUTCOME_UNKNOWN") from error

            if response.status_code in {429, 500, 502, 503, 504} and attempt == 0:
                continue
            if response.status_code >= 400:
                raise ProviderCallError(
                    kind=ProviderFailureKind.TRANSIENT if response.status_code in {429, 500, 502, 503, 504} else ProviderFailureKind.PERMANENT,
                    code="PROVIDER_TRANSIENT_FAILURE" if response.status_code in {429, 500, 502, 503, 504} else "PROVIDER_REQUEST_REJECTED",
                )
            latency_ms = int((monotonic() - started) * 1000)
            try:
                document = response.json()
                content = _content(document)
                payload = json.loads(content)
                if not isinstance(payload, dict) or set(payload) != {"items"}:
                    raise ValueError("Vision response JSON is not an object")
                metadata = _metadata(document, response.headers, self._model, latency_ms, self._price_tiers)
                result = VisionMealResult.model_validate({**payload, "metadata": metadata})
            except (ValueError, TypeError, json.JSONDecodeError, ValidationError) as error:
                raise ProviderCallError(kind=ProviderFailureKind.PERMANENT, code="PROVIDER_SCHEMA_INVALID") from error
            _safe_log(metadata, request.image.digest_sha256)
            return result
        raise AssertionError("unreachable retry loop")

    def _body(self, request: VisionMealRequest) -> dict[str, Any]:
        image_bytes = self._image_loader(request.image)
        if not image_bytes:
            raise ProviderCallError(kind=ProviderFailureKind.PERMANENT, code="VALIDATED_IMAGE_UNAVAILABLE")
        data_url = f"data:{request.image.mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
        return {
            "model": self._model,
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": data_url, "min_pixels": MIN_PIXELS, "max_pixels": request.pixel_budget}},
                {"type": "text", "text": VISION_JSON_CONTRACT},
            ]}],
            "response_format": {"type": "json_object"},
            "enable_thinking": False,
            "stream": False,
            "max_tokens": MAX_COMPLETION_TOKENS,
        }


def _content(document: object) -> str:
    if not isinstance(document, dict):
        raise ValueError("response is not an object")
    choices = document.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError("response has no choice")
    message = choices[0].get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str) or not message["content"]:
        raise ValueError("response has no JSON content")
    return message["content"]


@dataclass(frozen=True, slots=True)
class QwenPriceTier:
    max_input_tokens: int
    input_cny_per_m: Decimal
    output_cny_per_m: Decimal

    def __post_init__(self) -> None:
        if self.max_input_tokens <= 0:
            raise ValueError("max_input_tokens must be positive")
        for field_name in ("input_cny_per_m", "output_cny_per_m"):
            try:
                value = Decimal(str(getattr(self, field_name)))
            except (InvalidOperation, ValueError) as exc:
                raise ValueError(f"{field_name} must be a decimal value") from exc
            if value < 0:
                raise ValueError(f"{field_name} must not be negative")
            object.__setattr__(self, field_name, value)


def _metadata(document: dict[str, Any], headers: httpx.Headers, model: str, latency_ms: int, price_tiers: tuple[QwenPriceTier, ...]) -> VisionCallMetadataDTO:
    usage = document.get("usage")
    if not isinstance(usage, dict):
        raise ValueError("response has no usage")
    raw_prompt = _int(usage.get("prompt_tokens"))
    completion = _int(usage.get("completion_tokens"))
    details = usage.get("prompt_tokens_details") or usage.get("input_tokens_details") or {}
    image_tokens = _int(details.get("image_tokens") if isinstance(details, dict) else usage.get("image_tokens"), default=0)
    if image_tokens > raw_prompt:
        raise ValueError("image tokens exceed prompt tokens")
    text_prompt = raw_prompt - image_tokens
    tier = next((item for item in price_tiers if raw_prompt <= item.max_input_tokens), None)
    if tier is None:
        raise ValueError("input tokens exceed configured Qwen pricing tiers")
    request_id = _safe_identifier(headers.get("x-request-id") or document.get("id"))
    return VisionCallMetadataDTO(
        model_alias=model,
        provider_request_id=request_id,
        usage=VisionUsageDTO(image_tokens=image_tokens, prompt_tokens=text_prompt, completion_tokens=completion, cost_cny=(Decimal(raw_prompt) * tier.input_cny_per_m + Decimal(completion) * tier.output_cny_per_m) / Decimal("1000000")),
        latency_ms=latency_ms,
    )


def _int(value: object, *, default: int | None = None) -> int:
    if value is None and default is not None:
        return default
    if isinstance(value, int) and value >= 0:
        return value
    raise ValueError("usage value is invalid")


def _safe_identifier(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if 1 <= len(value) <= 128 else None


def _safe_log(metadata: VisionCallMetadataDTO, image_digest: str) -> None:
    """Only an irreversible digest and aggregate accounting are operationally useful."""

    LOGGER.info("", extra={"event": "qwen_vision_complete", "provider_request_id": metadata.provider_request_id, "model": metadata.model_alias, "tokens": metadata.usage.total_tokens, "cost": str(metadata.usage.cost_cny), "elapsed_ms": metadata.latency_ms, "image_digest": image_digest})
