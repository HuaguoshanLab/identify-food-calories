"""Scriptable Vision fake whose trace cannot become an image or model-output store."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from decimal import Decimal

from app.providers.reasoning.dto import ProviderCallError, ProviderFailureKind
from app.providers.vision.dto import (
    VisionCallMetadataDTO,
    VisionMealItemDTO,
    VisionMealRequest,
    VisionMealResult,
    VisionUsageDTO,
)


@dataclass(frozen=True, slots=True)
class FakeVisionProviderCall:
    operation: str
    call_id: str
    model_alias: str
    image_tokens: int
    prompt_tokens: int
    completion_tokens: int
    cost_usd: Decimal
    latency_ms: int


VisionOutcome = VisionMealResult | ProviderCallError


class FakeVisionModelProvider:
    """Queue exact observations or failures without retaining inputs or raw responses."""

    def __init__(self) -> None:
        self._outcomes: deque[VisionOutcome] = deque()
        self.calls: list[FakeVisionProviderCall] = []

    def queue_result(
        self,
        items: list[VisionMealItemDTO],
        *,
        usage: VisionUsageDTO | None = None,
        latency_ms: int = 0,
        model_alias: str = "fake-vision-v1",
    ) -> None:
        self._outcomes.append(
            VisionMealResult(items=items, metadata=_metadata(usage=usage, latency_ms=latency_ms, model_alias=model_alias))
        )

    def queue_schema_invalid(self) -> None:
        self.queue_error(kind=ProviderFailureKind.PERMANENT, code="PROVIDER_SCHEMA_INVALID")

    def queue_error(self, *, kind: ProviderFailureKind, code: str) -> None:
        self._outcomes.append(ProviderCallError(kind=kind, code=code, safe_message="Scripted vision provider failure."))

    async def analyze_meal_image(self, request: VisionMealRequest) -> VisionMealResult:
        del request  # The fake trace is intentionally incapable of retaining image references.
        outcome = self._outcomes.popleft() if self._outcomes else ProviderCallError(
            kind=ProviderFailureKind.PERMANENT,
            code="FAKE_UNSCRIPTED_CALL",
            safe_message="No scripted vision outcome is available.",
        )
        metadata = outcome.metadata if isinstance(outcome, VisionMealResult) else None
        metadata = metadata or _metadata()
        self.calls.append(
            FakeVisionProviderCall(
                operation="analyze_meal_image",
                call_id=metadata.call_id,
                model_alias=metadata.model_alias,
                image_tokens=metadata.usage.image_tokens,
                prompt_tokens=metadata.usage.prompt_tokens,
                completion_tokens=metadata.usage.completion_tokens,
                cost_usd=metadata.usage.cost_usd,
                latency_ms=metadata.latency_ms,
            )
        )
        if isinstance(outcome, ProviderCallError):
            raise outcome
        return outcome


def _metadata(
    *, usage: VisionUsageDTO | None = None, latency_ms: int = 0, model_alias: str = "fake-vision-v1"
) -> VisionCallMetadataDTO:
    return VisionCallMetadataDTO(
        model_alias=model_alias,
        usage=usage or VisionUsageDTO(image_tokens=0, prompt_tokens=0, completion_tokens=0, cost_usd=Decimal("0")),
        latency_ms=latency_ms,
    )
