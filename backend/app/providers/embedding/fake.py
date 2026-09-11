"""Offline scripted embedding provider with an intentionally non-sensitive trace."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from decimal import Decimal

from app.providers.embedding.dto import EmbeddingCallMetadataDTO, EmbeddingRequest, EmbeddingResult, EmbeddingUsageDTO, EmbeddingVectorDTO
from app.providers.reasoning.dto import ProviderCallError, ProviderFailureKind


@dataclass(frozen=True, slots=True)
class FakeEmbeddingProviderCall:
    """Safe accounting only: names and vectors must never become test traces."""

    operation: str
    text_type: str
    input_count: int


EmbeddingOutcome = EmbeddingResult | ProviderCallError


class FakeEmbeddingProvider:
    """Replay prepared outcomes without network access or sensitive call retention."""

    def __init__(self) -> None:
        self._outcomes: deque[EmbeddingOutcome] = deque()
        self.calls: list[FakeEmbeddingProviderCall] = []

    def queue_result(self, vectors: tuple[tuple[float, ...], ...], *, model_alias: str = "fake-embedding-v1", embedding_version: str = "embedding.v1") -> None:
        self._outcomes.append(EmbeddingResult(input_count=len(vectors), vectors=tuple(EmbeddingVectorDTO(values=vector) for vector in vectors), metadata=_metadata(model_alias=model_alias, embedding_version=embedding_version)))

    def queue_error(self, *, kind: ProviderFailureKind, code: str) -> None:
        self._outcomes.append(ProviderCallError(kind=kind, code=code, safe_message="Scripted embedding provider failure."))

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult:
        input_count = len(request.names)
        text_type = request.text_type
        del request  # The fake deliberately cannot retain normalized food names.
        outcome = self._outcomes.popleft() if self._outcomes else ProviderCallError(kind=ProviderFailureKind.PERMANENT, code="FAKE_UNSCRIPTED_CALL", safe_message="No scripted embedding outcome is available.")
        self.calls.append(FakeEmbeddingProviderCall(operation="embed", text_type=text_type, input_count=input_count))
        if isinstance(outcome, ProviderCallError):
            raise outcome
        if outcome.input_count != input_count:
            raise ProviderCallError(kind=ProviderFailureKind.PERMANENT, code="FAKE_RESULT_COUNT_MISMATCH", safe_message="Scripted embedding outcome count does not match the request.")
        return outcome


def _metadata(*, model_alias: str, embedding_version: str) -> EmbeddingCallMetadataDTO:
    return EmbeddingCallMetadataDTO(model_alias=model_alias, embedding_version=embedding_version, usage=EmbeddingUsageDTO(input_tokens=0, total_tokens=0, cost_cny=Decimal("0")), latency_ms=0)
