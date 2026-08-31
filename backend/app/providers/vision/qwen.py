"""Qwen-VL HTTP adapter: transient image bytes exist only inside one outbound request."""

from __future__ import annotations

import base64
import json
import logging
from collections.abc import Callable, Mapping
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
MIN_PIXELS = 3_136


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
        price_snapshot: Mapping[str, str | Decimal],
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
        self._input_price = _price(price_snapshot, "input_usd_per_m")
        self._output_price = _price(price_snapshot, "output_usd_per_m")
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
            endpoint=settings.qwen_base_url,
            timeout_seconds=settings.vision_timeout_seconds,
            max_pixels=settings.vision_max_pixels,
            price_snapshot={"input_usd_per_m": settings.qwen_input_usd_per_m or Decimal("0"), "output_usd_per_m": settings.qwen_output_usd_per_m or Decimal("0")},
            image_loader=lambda reference: repository.read_path(reference).read_bytes(),
        )

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
                metadata = _metadata(document, response.headers, self._model, latency_ms, self._input_price, self._output_price)
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
                {"type": "text", "text": "Return JSON only. Identify meal items, preparation, portion clues, estimated grams and confidence. Do not provide nutrition values or reasoning."},
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


def _metadata(document: dict[str, Any], headers: httpx.Headers, model: str, latency_ms: int, input_price: Decimal, output_price: Decimal) -> VisionCallMetadataDTO:
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
    request_id = _safe_identifier(headers.get("x-request-id") or document.get("id"))
    return VisionCallMetadataDTO(
        model_alias=model,
        provider_request_id=request_id,
        usage=VisionUsageDTO(image_tokens=image_tokens, prompt_tokens=text_prompt, completion_tokens=completion, cost_usd=(Decimal(raw_prompt) * input_price + Decimal(completion) * output_price) / Decimal("1000000")),
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


def _price(snapshot: Mapping[str, str | Decimal], name: str) -> Decimal:
    try:
        value = Decimal(str(snapshot[name]))
    except (KeyError, InvalidOperation) as error:
        raise ValueError(f"price snapshot missing {name}") from error
    if value < 0:
        raise ValueError(f"price snapshot {name} must be non-negative")
    return value


def _safe_log(metadata: VisionCallMetadataDTO, image_digest: str) -> None:
    """Only an irreversible digest and aggregate accounting are operationally useful."""

    LOGGER.info("qwen_vision_complete request_id=%s model=%s tokens=%s cost=%s latency_ms=%s image_digest=%s", metadata.provider_request_id, metadata.model_alias, metadata.usage.total_tokens, metadata.usage.cost_usd, metadata.latency_ms, image_digest)
