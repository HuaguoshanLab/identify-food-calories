"""DeepSeek Responses adapter with a narrow, safe, retry-bounded provider boundary."""

from __future__ import annotations
from app.core.logging import observed

import json
import logging
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from time import monotonic
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.tracing import DisabledTracingRuntime, TracingRuntime
from app.providers.reasoning.dto import (
    ApplyCorrectionRequest,
    ApplyCorrectionResult,
    CorrectionDTO,
    ParseMealRequest,
    ParseMealResult,
    ParsedMealDTO,
    ProviderCallError,
    ProviderCallMetadataDTO,
    ProviderFailureKind,
    ProviderUsageDTO,
    WeeklyReviewOutputDTO,
    WeeklyReviewRequest,
    WeeklyReviewResult,
)


LOGGER = logging.getLogger(__name__)
DEEPSEEK_RESPONSES_URL = "https://api.deepseek.com/responses"
MAX_OUTPUT_TOKENS = 800
PARSE_MEAL_INSTRUCTIONS = (
    "Return only JSON matching the supplied JSON schema. Do not include reasoning, "
    "nutrition values, or text outside JSON. For every item, item_id is an internal "
    "short identifier only. food_name must be the actual food name from the user's "
    "description, never item_id, item_1, food_1, or another placeholder. catalog_query "
    "is optional; when present it must be a food-name query and must never be an internal "
    "item identifier or placeholder."
)


class DeepSeekReasoningModelProvider:
    """Call only the Responses API; never expose vendor bodies beyond this module."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: int,
        price_snapshot: Mapping[str, str | Decimal],
        transport: httpx.AsyncBaseTransport | None = None,
        tracing: TracingRuntime | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("DeepSeek API key is required")
        if model != "deepseek-v4-flash":
            raise ValueError("DeepSeek model must be the pinned deepseek-v4-flash revision")
        if timeout_seconds != 20:
            raise ValueError("DeepSeek timeout must be exactly 20 seconds")
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._input_price = _price(price_snapshot, "input_usd_per_m")
        self._output_price = _price(price_snapshot, "output_usd_per_m")
        self._transport = transport
        self._tracing = tracing or DisabledTracingRuntime()

    @observed("provider")
    async def parse_meal(self, request: ParseMealRequest) -> ParseMealResult:
        payload, metadata = await self._request(
            operation="parse_meal",
            user_text=request.meal_description,
            schema=ParsedMealDTO,
            instructions=PARSE_MEAL_INSTRUCTIONS,
        )
        try:
            return ParseMealResult(value=ParsedMealDTO.model_validate(payload), metadata=metadata)
        except ValidationError as error:
            raise _schema_error(metadata) from error

    @observed("provider")
    async def apply_correction(self, request: ApplyCorrectionRequest) -> ApplyCorrectionResult:
        payload, metadata = await self._request(
            operation="apply_correction",
            user_text=request.correction_text,
            schema=CorrectionDTO,
        )
        try:
            return ApplyCorrectionResult(value=CorrectionDTO.model_validate(payload), metadata=metadata)
        except ValidationError as error:
            raise _schema_error(metadata) from error

    @observed("provider")
    async def generate_weekly_review(self, request: WeeklyReviewRequest) -> WeeklyReviewResult:
        payload, metadata = await self._request(
            operation="generate_weekly_review",
            user_text=request.facts.model_dump_json(),
            schema=WeeklyReviewOutputDTO,
            instructions=(
                "Return only JSON matching the supplied JSON schema. Use only the supplied "
                "de-identified weekly facts. Give one to three optional general dietary "
                "references; never output numbers, diagnosis, disease, medication, treatment, "
                "extreme restriction, coercive language, or reasoning."
            ),
            max_output_tokens=360,
        )
        try:
            return WeeklyReviewResult(
                value=WeeklyReviewOutputDTO.model_validate(payload), metadata=metadata
            )
        except ValidationError as error:
            raise _schema_error(metadata) from error

    async def _request(
        self,
        *,
        operation: str,
        user_text: str,
        schema: type[ParsedMealDTO] | type[CorrectionDTO] | type[WeeklyReviewOutputDTO],
        instructions: str | None = None,
        max_output_tokens: int = MAX_OUTPUT_TOKENS,
    ) -> tuple[dict[str, Any], ProviderCallMetadataDTO]:
        body = {
            "model": self._model,
            "instructions": instructions or (
                "Return only JSON matching the supplied JSON schema. Do not include reasoning, "
                "nutrition values, or text outside JSON."
            ),
            "input": [{"role": "user", "content": user_text}],
            "reasoning": {"effort": "none"},
            "max_output_tokens": max_output_tokens,
            "store": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": operation,
                    "schema": schema.model_json_schema(),
                }
            },
        }
        started = monotonic()
        for attempt in range(2):
            try:
                with self._tracing.span(
                    "agent.provider",
                    {"provider.model": self._model, "node.name": operation},
                ) as trace_span:
                    if trace_span is not None:
                        trace_span.update(
                            input={
                                "operation": operation,
                                "messages": [{"role": "user", "content": user_text}],
                            }
                        )
                    async with httpx.AsyncClient(
                        timeout=httpx.Timeout(self._timeout_seconds), transport=self._transport
                    ) as client:
                        response = await client.post(
                            DEEPSEEK_RESPONSES_URL,
                            headers={"Authorization": f"Bearer {self._api_key}"},
                            json=body,
                        )
                    latency_ms = int((monotonic() - started) * 1000)
                    if response.status_code in {429, 500, 502, 503, 504} and attempt == 0:
                        continue
                    if response.status_code >= 400:
                        raise ProviderCallError(
                            kind=(
                                ProviderFailureKind.TRANSIENT
                                if response.status_code in {429, 500, 502, 503, 504}
                                else ProviderFailureKind.PERMANENT
                            ),
                            code=("PROVIDER_TRANSIENT_FAILURE" if response.status_code >= 500 or response.status_code == 429 else "PROVIDER_REQUEST_REJECTED"),
                        )
                    try:
                        document = response.json()
                        content = _response_output_text(document)
                        payload = json.loads(content)
                        if not isinstance(payload, dict):
                            raise ValueError("response JSON is not an object")
                        metadata = _metadata(
                            document=document,
                            headers=response.headers,
                            model=self._model,
                            latency_ms=latency_ms,
                            input_price=self._input_price,
                            output_price=self._output_price,
                        )
                    except (ValueError, TypeError, json.JSONDecodeError, ValidationError) as error:
                        raise _schema_error(None) from error
                    if trace_span is not None:
                        trace_span.update(
                            output=payload,
                            usage_details={
                                "input": metadata.usage.prompt_tokens,
                                "output": metadata.usage.completion_tokens,
                                "total": metadata.usage.total_tokens or 0,
                            },
                            cost_details={"total": float(metadata.usage.cost_usd)},
                        )
            except (httpx.TimeoutException, httpx.NetworkError, httpx.ProtocolError) as error:
                # Once a request is prepared, transport loss is not provably pre-send. Never retry.
                raise ProviderCallError(
                    kind=ProviderFailureKind.OUTCOME_UNKNOWN,
                    code="PROVIDER_OUTCOME_UNKNOWN",
                ) from error

            _safe_log(metadata)
            return payload, metadata
        raise AssertionError("unreachable retry loop")


def _response_output_text(document: object) -> str:
    if not isinstance(document, dict) or document.get("status") != "completed":
        raise ValueError("response was not completed")
    output = document.get("output")
    if not isinstance(output, list):
        raise ValueError("response has no output")
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, dict) and part.get("type") == "output_text":
                text = part.get("text")
                if isinstance(text, str) and text:
                    return text
    raise ValueError("response has no JSON output text")


def _metadata(
    *,
    document: dict[str, Any],
    headers: httpx.Headers,
    model: str,
    latency_ms: int,
    input_price: Decimal,
    output_price: Decimal,
) -> ProviderCallMetadataDTO:
    usage = document.get("usage")
    if not isinstance(usage, dict):
        raise ValueError("response has no usage")
    input_tokens = _int(usage.get("input_tokens"))
    output_tokens = _int(usage.get("output_tokens"))
    provider_request_id = _safe_identifier(headers.get("x-request-id") or document.get("id"))
    cost = (Decimal(input_tokens) * input_price + Decimal(output_tokens) * output_price) / Decimal(
        "1000000"
    )
    return ProviderCallMetadataDTO(
        model_alias=model,
        provider_request_id=provider_request_id,
        usage=ProviderUsageDTO(
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
            total_tokens=_int(usage.get("total_tokens"), default=input_tokens + output_tokens),
            cost_usd=cost,
        ),
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
    normalized = value.strip()
    return normalized if 1 <= len(normalized) <= 128 else None


def _price(snapshot: Mapping[str, str | Decimal], name: str) -> Decimal:
    try:
        value = Decimal(str(snapshot[name]))
    except (KeyError, InvalidOperation) as error:
        raise ValueError(f"price snapshot missing {name}") from error
    if value < 0:
        raise ValueError(f"price snapshot {name} must be non-negative")
    return value


def _schema_error(metadata: ProviderCallMetadataDTO | None) -> ProviderCallError:
    return ProviderCallError(
        kind=ProviderFailureKind.PERMANENT,
        code="PROVIDER_SCHEMA_INVALID",
        metadata=metadata,
    )


def _safe_log(metadata: ProviderCallMetadataDTO) -> None:
    """Log only identifiers and accounting values, never payload, output, or credentials."""

    LOGGER.info("", extra={"event": "deepseek_call_complete", "provider_request_id": metadata.provider_request_id, "model": metadata.model_alias, "tokens": metadata.usage.total_tokens, "cost": str(metadata.usage.cost_usd), "elapsed_ms": metadata.latency_ms})
