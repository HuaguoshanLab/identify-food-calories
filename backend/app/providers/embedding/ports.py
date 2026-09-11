"""Narrow embedding port; callers cannot depend on a vendor transport."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.providers.embedding.dto import EmbeddingRequest, EmbeddingResult


@runtime_checkable
class EmbeddingProvider(Protocol):
    async def embed(self, request: EmbeddingRequest) -> EmbeddingResult: ...
