"""Offline tests for the strict, context-free embedding-provider boundary."""

from __future__ import annotations

import asyncio
from dataclasses import fields

import pytest
from pydantic import ValidationError

from app.providers.embedding.dto import EMBEDDING_DIMENSION, EmbeddingCallMetadataDTO, EmbeddingRequest, EmbeddingResult, EmbeddingUsageDTO, EmbeddingVectorDTO
from app.providers.embedding.fake import FakeEmbeddingProvider, FakeEmbeddingProviderCall
from app.providers.embedding.ports import EmbeddingProvider
from app.providers.reasoning.dto import ProviderCallError, ProviderFailureKind


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
