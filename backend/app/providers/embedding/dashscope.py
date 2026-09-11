"""Bounded DashScope adapter for normalized catalog names only."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from time import monotonic
from typing import Protocol
import httpx
from pydantic import ValidationError

from app.core.config import Settings
from app.core.embedding_budget import (
    EmbeddingBudgetReservation,
    EmbeddingBudgetUnavailable,
    require_ledger_amount,
    round_cost_up_for_ledger,
)
from app.providers.embedding.dto import (
    EMBEDDING_DIMENSION,
    EmbeddingCallMetadataDTO,
    EmbeddingRequest,
    EmbeddingResult,
    EmbeddingUsageDTO,
    EmbeddingVectorDTO,
)
from app.providers.reasoning.dto import ProviderCallError, ProviderFailureKind


DASHSCOPE_EMBEDDING_URL = (
    "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"
)
PINNED_MODEL = "text-embedding-v4"
PINNED_ADAPTER_VERSION = "dashscope-text-embedding-v4-1024.v1"
MAX_HTTP_ATTEMPTS = 2


class EmbeddingBudgetLedger(Protocol):
    """Small accounting port keeps the HTTP adapter free of persistence details."""

    def reserve(self, *, amount_cny: Decimal, cap_cny: Decimal) -> EmbeddingBudgetReservation | None: ...

    def settle(self, reservation: EmbeddingBudgetReservation, *, actual_cost_cny: Decimal) -> None: ...


class DashScopeEmbeddingProvider:
    """Call the pinned DashScope embedding endpoint without exposing vendor bodies."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        dimension: int,
        timeout_seconds: float,
        input_cny_per_m: Decimal,
        single_call_cap_cny: Decimal,
        period_cap_cny: Decimal,
        price_snapshot_version: str,
        adapter_version: str = PINNED_ADAPTER_VERSION,
        budget_ledger: EmbeddingBudgetLedger | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key.strip() or model != PINNED_MODEL or dimension != EMBEDDING_DIMENSION:
            raise ValueError("DashScope model, dimension, and credentials are invalid")
        if timeout_seconds != 1.5:
            raise ValueError("DashScope embedding timeout must be exactly 1.5 seconds")
        if adapter_version != PINNED_ADAPTER_VERSION or not price_snapshot_version.strip():
            raise ValueError("DashScope adapter or price snapshot version is invalid")
        if any(value <= 0 for value in (input_cny_per_m, single_call_cap_cny, period_cap_cny)):
            raise ValueError("DashScope price and cost caps must be positive")
        try:
            require_ledger_amount(single_call_cap_cny, variable="DashScope single-call cost cap")
            require_ledger_amount(period_cap_cny, variable="DashScope period cost cap")
            require_ledger_amount(
                single_call_cap_cny * MAX_HTTP_ATTEMPTS,
                variable="DashScope retry reservation amount",
            )
        except ValueError as error:
            raise ValueError("DashScope cost caps are incompatible with the budget ledger") from error
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._input_cny_per_m = input_cny_per_m
        self._single_call_cap_cny = single_call_cap_cny
        self._period_cap_cny = period_cap_cny
        self._price_snapshot_version = price_snapshot_version
        self._adapter_version = adapter_version
        self._budget_ledger = budget_ledger
        self._transport = transport

    @classmethod
    def from_settings(cls, settings: Settings, *, budget_ledger: EmbeddingBudgetLedger | None = None) -> DashScopeEmbeddingProvider:
        required = (
            settings.dashscope_api_key,
            settings.embedding_model,
            settings.embedding_dimension,
            settings.embedding_price_snapshot_version,
            settings.embedding_input_cny_per_m,
            settings.embedding_single_call_cap_cny,
            settings.embedding_period_cap_cny,
            settings.embedding_timeout_seconds,
        )
        if any(value is None for value in required):
            raise ValueError("DashScope embedding Settings are incomplete")
        assert settings.dashscope_api_key is not None
        return cls(
            api_key=settings.dashscope_api_key.get_secret_value(),
            model=settings.embedding_model or "",
            dimension=settings.embedding_dimension or 0,
            timeout_seconds=settings.embedding_timeout_seconds or 0,
            input_cny_per_m=settings.embedding_input_cny_per_m or Decimal("0"),
            single_call_cap_cny=settings.embedding_single_call_cap_cny or Decimal("0"),
            period_cap_cny=settings.embedding_period_cap_cny or Decimal("0"),
            price_snapshot_version=settings.embedding_price_snapshot_version or "",
            adapter_version=settings.embedding_adapter_version or PINNED_ADAPTER_VERSION,
            budget_ledger=budget_ledger,
        )

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        if self._budget_ledger is None:
            raise ProviderCallError(
                kind=ProviderFailureKind.PERMANENT, code="PROVIDER_BUDGET_LEDGER_UNAVAILABLE"
            )
        try:
            reservation = self._budget_ledger.reserve(
                # A retry is another vendor request and can be billable even if its
                # first response is a 5xx.  Reserve the whole bounded attempt budget
                # atomically before the first request; reserving only one call here
                # would let concurrent workers spend beyond the monthly cap.
                amount_cny=self._single_call_cap_cny * MAX_HTTP_ATTEMPTS,
                cap_cny=self._period_cap_cny,
            )
        except EmbeddingBudgetUnavailable as error:
            raise ProviderCallError(
                kind=ProviderFailureKind.PERMANENT, code="PROVIDER_BUDGET_LEDGER_UNAVAILABLE"
            ) from error
        if reservation is None:
            raise ProviderCallError(
                kind=ProviderFailureKind.PERMANENT, code="PROVIDER_PERIOD_COST_CAP_EXCEEDED"
            )
        body = {
            "model": self._model,
            "input": {"texts": list(request.names)},
            "parameters": {
                "text_type": request.text_type,
                "dimension": EMBEDDING_DIMENSION,
                "output_type": "dense",
            },
        }
        started = monotonic()
        retry_cost_exposure = Decimal("0")
        for attempt in range(MAX_HTTP_ATTEMPTS):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(self._timeout_seconds), transport=self._transport
                ) as client:
                    response = await client.post(
                        DASHSCOPE_EMBEDDING_URL,
                        headers={"Authorization": f"Bearer {self._api_key}"},
                        json=body,
                    )
            except httpx.TimeoutException as error:
                raise ProviderCallError(
                    kind=ProviderFailureKind.TRANSIENT, code="PROVIDER_TIMEOUT"
                ) from error
            except (httpx.NetworkError, httpx.ProtocolError) as error:
                raise ProviderCallError(
                    kind=ProviderFailureKind.OUTCOME_UNKNOWN, code="PROVIDER_OUTCOME_UNKNOWN"
                ) from error

            if response.status_code in {429, 500, 502, 503, 504} and attempt == 0:
                # These statuses do not prove the provider skipped billing.  Retain
                # one full-call allowance before retrying, then settle the final
                # reservation with that conservative exposure plus known success cost.
                retry_cost_exposure += self._single_call_cap_cny
                continue
            if response.status_code >= 400:
                raise ProviderCallError(
                    kind=(ProviderFailureKind.TRANSIENT if response.status_code in {429, 500, 502, 503, 504} else ProviderFailureKind.PERMANENT),
                    code=("PROVIDER_TRANSIENT_FAILURE" if response.status_code in {429, 500, 502, 503, 504} else "PROVIDER_REQUEST_REJECTED"),
                )
            try:
                result = _result(
                    document=response.json(), request=request, model=self._model,
                    adapter_version=self._adapter_version,
                    price_snapshot_version=self._price_snapshot_version,
                    input_cny_per_m=self._input_cny_per_m,
                    single_call_cap_cny=self._single_call_cap_cny,
                    latency_ms=int((monotonic() - started) * 1000),
                )
            except (TypeError, ValueError, InvalidOperation, ValidationError) as error:
                raise ProviderCallError(
                    kind=ProviderFailureKind.PERMANENT, code="PROVIDER_SCHEMA_INVALID"
                ) from error
            try:
                self._budget_ledger.settle(
                    reservation,
                    actual_cost_cny=retry_cost_exposure + result.metadata.usage.cost_cny,
                )
            except EmbeddingBudgetUnavailable as error:
                raise ProviderCallError(
                    kind=ProviderFailureKind.PERMANENT, code="PROVIDER_BUDGET_LEDGER_UNAVAILABLE"
                ) from error
            return result
        raise AssertionError("unreachable retry loop")


def _result(
    *, document: object, request: EmbeddingRequest, model: str, adapter_version: str,
    price_snapshot_version: str, input_cny_per_m: Decimal, single_call_cap_cny: Decimal,
    latency_ms: int,
) -> EmbeddingResult:
    if not isinstance(document, dict):
        raise ValueError("response is not an object")
    output = document.get("output")
    usage = document.get("usage")
    if not isinstance(output, dict) or not isinstance(usage, dict):
        raise ValueError("response has no output or usage")
    embeddings = output.get("embeddings")
    if not isinstance(embeddings, list) or len(embeddings) != len(request.names):
        raise ValueError("response embedding count is invalid")
    vectors: list[EmbeddingVectorDTO] = []
    for index, item in enumerate(embeddings):
        if not isinstance(item, dict) or item.get("text_index") not in {None, index}:
            raise ValueError("response embedding index is invalid")
        raw_vector = item.get("embedding")
        if not isinstance(raw_vector, list) or any(
            not isinstance(value, (int, float)) or isinstance(value, bool)
            for value in raw_vector
        ):
            raise ValueError("response embedding vector is invalid")
        vectors.append(EmbeddingVectorDTO(values=tuple(float(value) for value in raw_vector)))
    total_tokens = usage.get("total_tokens")
    if not isinstance(total_tokens, int) or total_tokens < 0:
        raise ValueError("response token usage is invalid")
    cost = Decimal(total_tokens) * input_cny_per_m / Decimal("1000000")
    if cost > single_call_cap_cny:
        raise ProviderCallError(kind=ProviderFailureKind.PERMANENT, code="PROVIDER_COST_CAP_EXCEEDED")
    try:
        # Metadata and settlement must agree on the conservatively rounded
        # amount that the NUMERIC(18, 8) ledger can represent.
        cost = round_cost_up_for_ledger(cost)
    except ValueError as error:
        raise ProviderCallError(
            kind=ProviderFailureKind.PERMANENT, code="PROVIDER_COST_ACCOUNTING_INVALID"
        ) from error
    request_id = document.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip() or len(request_id.strip()) > 128:
        request_id = None
    return EmbeddingResult(
        input_count=len(request.names), vectors=tuple(vectors),
        metadata=EmbeddingCallMetadataDTO(
            model_alias=model,
            embedding_version=f"{adapter_version}:{price_snapshot_version}",
            provider_request_id=request_id,
            usage=EmbeddingUsageDTO(input_tokens=total_tokens, total_tokens=total_tokens, cost_cny=cost),
            latency_ms=latency_ms,
        ),
    )
