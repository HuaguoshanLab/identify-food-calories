"""Offline tests for the strict, context-free embedding-provider boundary."""

from __future__ import annotations

import asyncio
import json
from dataclasses import fields
from decimal import Decimal

import httpx
import pytest
from pydantic import ValidationError

from app.core.config import ConfigurationError, Settings
from app.core.embedding_budget import EmbeddingBudgetReservation
from app.providers.embedding.dto import EMBEDDING_DIMENSION, EmbeddingCallMetadataDTO, EmbeddingRequest, EmbeddingResult, EmbeddingUsageDTO, EmbeddingVectorDTO
from app.providers.embedding.factory import create_embedding_provider
from app.providers.embedding.fake import FakeEmbeddingProvider, FakeEmbeddingProviderCall
from app.providers.embedding.ports import EmbeddingProvider
from app.providers.reasoning.dto import ProviderCallError, ProviderFailureKind


class _BudgetLedger:
    def __init__(self, *, allow: bool = True) -> None:
        self.allow = allow
        self.reserved: list[tuple[Decimal, Decimal]] = []
        self.settled: list[Decimal] = []

    def reserve(self, *, amount_cny: Decimal, cap_cny: Decimal) -> EmbeddingBudgetReservation | None:
        self.reserved.append((amount_cny, cap_cny))
        return EmbeddingBudgetReservation(period_key="2026-09", amount_cny=amount_cny) if self.allow else None

    def settle(self, reservation: EmbeddingBudgetReservation, *, actual_cost_cny: Decimal) -> None:
        assert reservation.amount_cny >= actual_cost_cny
        self.settled.append(actual_cost_cny)


def _request(*, names: tuple[str, ...] = ("米饭",), text_type: str = "query") -> EmbeddingRequest:
    return EmbeddingRequest(names=names, text_type=text_type, model_alias="embedding-test")


def _metadata() -> EmbeddingCallMetadataDTO:
    return EmbeddingCallMetadataDTO(model_alias="embedding-test", embedding_version="embedding.v1", usage=EmbeddingUsageDTO(input_tokens=1, total_tokens=1, cost_cny="0"), latency_ms=0)


def test_request_allows_one_normalized_query_and_up_to_ten_catalog_documents() -> None:
    assert _request().text_type == "query"
    assert len(_request(names=tuple(f"food-{number}" for number in range(10)), text_type="document").names) == 10
    with pytest.raises(ValidationError):
        _request(names=("米饭", "面条"))
    with pytest.raises(ValidationError):
        _request(names=(" 米饭",))
    with pytest.raises(ValidationError):
        _request(names=tuple(f"food-{number}" for number in range(11)), text_type="document")


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
def test_response_rejects_non_finite_or_wrong_dimension_vectors(bad_value: float) -> None:
    with pytest.raises(ValidationError):
        EmbeddingVectorDTO(values=tuple([0.0] * (EMBEDDING_DIMENSION - 1)))
    with pytest.raises(ValidationError):
        EmbeddingVectorDTO(values=(bad_value,) + tuple([0.0] * (EMBEDDING_DIMENSION - 1)))
    vector = EmbeddingVectorDTO(values=tuple([0.0] * EMBEDDING_DIMENSION))
    with pytest.raises(ValidationError):
        EmbeddingResult(input_count=2, vectors=(vector,), metadata=_metadata())


def test_fake_is_scripted_offline_and_traces_only_safe_counters() -> None:
    fake: EmbeddingProvider = FakeEmbeddingProvider()
    assert isinstance(fake, EmbeddingProvider)
    assert {field.name for field in fields(FakeEmbeddingProviderCall)} == {"operation", "text_type", "input_count"}
    with pytest.raises(ProviderCallError) as unscripted:
        asyncio.run(fake.embed(_request()))
    assert unscripted.value.code == "FAKE_UNSCRIPTED_CALL"
    scripted = FakeEmbeddingProvider()
    scripted.queue_result((tuple([0.25] * EMBEDDING_DIMENSION),))
    assert asyncio.run(scripted.embed(_request())).input_count == 1
    assert scripted.calls == [FakeEmbeddingProviderCall(operation="embed", text_type="query", input_count=1)]
    scripted.queue_error(kind=ProviderFailureKind.PERMANENT, code="SCRIPTED_FAILURE")
    with pytest.raises(ProviderCallError, match="Scripted embedding provider failure"):
        asyncio.run(scripted.embed(_request()))


def _dashscope_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "local",
        "embedding_provider_mode": "dashscope",
        "dashscope_api_key": "test-key",
        "embedding_model": "text-embedding-v4",
        "embedding_dimension": EMBEDDING_DIMENSION,
        "embedding_price_snapshot_version": "dashscope-2026-09-10",
        "embedding_input_cny_per_m": Decimal("0.5"),
        "embedding_single_call_cap_cny": Decimal("0.01"),
        "embedding_period_cap_cny": Decimal("20"),
        "embedding_timeout_seconds": 1.5,
    }
    values.update(overrides)
    return Settings(**values)


def test_factory_uses_fake_in_test_without_credentials_or_network() -> None:
    assert isinstance(create_embedding_provider(app_env="test"), FakeEmbeddingProvider)
    with pytest.raises(ConfigurationError):
        create_embedding_provider(app_env="production", provider_mode="fake")


def test_test_only_embedding_outcome_script_is_closed_and_offline() -> None:
    scripted = Settings(
        app_env="test", test_embedding_outcomes="success,permanent_failure"
    )
    provider = create_embedding_provider(scripted)
    assert isinstance(provider, FakeEmbeddingProvider)
    assert asyncio.run(provider.embed(_request())).input_count == 1
    with pytest.raises(ProviderCallError) as failure:
        asyncio.run(provider.embed(_request()))
    assert failure.value.code == "E2E_SCRIPTED_FAILURE"
    with pytest.raises(ValidationError, match="only allowed"):
        Settings(app_env="local", test_embedding_outcomes="success")
    with pytest.raises(ValidationError, match="accepts only"):
        Settings(app_env="test", test_embedding_outcomes="success,network")


def test_factory_is_fail_closed_but_allows_explicit_text_fallback() -> None:
    assert create_embedding_provider(app_env="local", provider_mode="disabled") is None
    with pytest.raises(ConfigurationError, match="Settings"):
        create_embedding_provider(app_env="local", provider_mode="dashscope")
    with pytest.raises(ConfigurationError, match="DASHSCOPE_API_KEY"):
        create_embedding_provider(_dashscope_settings(dashscope_api_key=None))
    provider = create_embedding_provider(_dashscope_settings())
    assert provider.__class__.__name__ == "DashScopeEmbeddingProvider"


def test_dashscope_retries_once_and_validates_safe_response_boundary() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        assert request.url == httpx.URL("https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding")
        assert json.loads(request.content) == {
            "model": "text-embedding-v4",
            "input": {"texts": ["米饭"]},
            "parameters": {"text_type": "query", "dimension": EMBEDDING_DIMENSION, "output_type": "dense"},
        }
        if attempts == 1:
            return httpx.Response(429, text="provider body must not escape")
        return httpx.Response(200, json={
            "request_id": "safe-request-id",
            "output": {"embeddings": [{"text_index": 0, "embedding": [0.25] * EMBEDDING_DIMENSION}]},
            "usage": {"total_tokens": 3},
        })

    from app.providers.embedding.dashscope import DashScopeEmbeddingProvider

    ledger = _BudgetLedger()
    provider = DashScopeEmbeddingProvider(
        api_key="test-key",
        model="text-embedding-v4",
        dimension=EMBEDDING_DIMENSION,
        timeout_seconds=1.5,
        input_cny_per_m=Decimal("0.5"),
        single_call_cap_cny=Decimal("0.01"),
        period_cap_cny=Decimal("20"),
        price_snapshot_version="dashscope-2026-09-10",
        budget_ledger=ledger,
        transport=httpx.MockTransport(handler),
    )
    result = asyncio.run(provider.embed(_request()))
    assert attempts == 2
    assert result.metadata.usage.input_tokens == 3
    assert result.metadata.usage.cost_cny == Decimal("0.0000015")
    assert ledger.reserved == [(Decimal("0.01"), Decimal("20"))]
    assert ledger.settled == [Decimal("0.0000015")]


@pytest.mark.parametrize(
    ("response_factory", "expected_code"),
    [
        (lambda: httpx.Response(400, text="sensitive body"), "PROVIDER_REQUEST_REJECTED"),
        (lambda: httpx.Response(200, content=b'{"output":{"embeddings":[{"embedding":[NaN]}]},"usage":{"total_tokens":1}}'), "PROVIDER_SCHEMA_INVALID"),
        (lambda: httpx.Response(200, content=b'{"output":{"embeddings":[{"embedding":[Infinity]}]},"usage":{"total_tokens":1}}'), "PROVIDER_SCHEMA_INVALID"),
        (lambda: httpx.Response(200, json={"output": {"embeddings": [{"embedding": [0.0] * (EMBEDDING_DIMENSION - 1)}]}, "usage": {"total_tokens": 1}}), "PROVIDER_SCHEMA_INVALID"),
    ],
)
def test_dashscope_never_leaks_response_body(response_factory: object, expected_code: str) -> None:
    from app.providers.embedding.dashscope import DashScopeEmbeddingProvider

    provider = DashScopeEmbeddingProvider(
        api_key="test-key", model="text-embedding-v4", dimension=EMBEDDING_DIMENSION,
        timeout_seconds=1.5, input_cny_per_m=Decimal("0.5"), single_call_cap_cny=Decimal("0.01"),
        period_cap_cny=Decimal("20"), price_snapshot_version="dashscope-2026-09-10",
        budget_ledger=_BudgetLedger(),
        transport=httpx.MockTransport(lambda request: response_factory()),  # type: ignore[operator]
    )
    with pytest.raises(ProviderCallError) as error:
        asyncio.run(provider.embed(_request()))
    assert error.value.code == expected_code
    assert "sensitive body" not in str(error.value)


def test_dashscope_timeout_maps_to_safe_code() -> None:
    from app.providers.embedding.dashscope import DashScopeEmbeddingProvider

    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("provider body must not escape", request=request)

    provider = DashScopeEmbeddingProvider(
        api_key="test-key", model="text-embedding-v4", dimension=EMBEDDING_DIMENSION,
        timeout_seconds=1.5, input_cny_per_m=Decimal("0.5"), single_call_cap_cny=Decimal("0.01"),
        period_cap_cny=Decimal("20"), price_snapshot_version="dashscope-2026-09-10",
        budget_ledger=_BudgetLedger(),
        transport=httpx.MockTransport(timeout),
    )
    with pytest.raises(ProviderCallError) as error:
        asyncio.run(provider.embed(_request()))
    assert error.value.code == "PROVIDER_TIMEOUT"
    assert "provider body" not in str(error.value)


def test_dashscope_rejects_period_cap_before_network_call() -> None:
    from app.providers.embedding.dashscope import DashScopeEmbeddingProvider

    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200)

    provider = DashScopeEmbeddingProvider(
        api_key="test-key", model="text-embedding-v4", dimension=EMBEDDING_DIMENSION,
        timeout_seconds=1.5, input_cny_per_m=Decimal("0.5"), single_call_cap_cny=Decimal("0.01"),
        period_cap_cny=Decimal("20"), price_snapshot_version="dashscope-2026-09-10",
        budget_ledger=_BudgetLedger(allow=False), transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ProviderCallError) as error:
        asyncio.run(provider.embed(_request()))

    assert error.value.code == "PROVIDER_PERIOD_COST_CAP_EXCEEDED"
    assert called is False
