"""Deterministic reasoning-provider substitute for tests and local development."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from decimal import Decimal

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
)


@dataclass(frozen=True, slots=True)
class FakeProviderCall:
    """Audit-friendly trace deliberately excluding request/response bodies."""

    operation: str
    call_id: str
    model_alias: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: Decimal
    latency_ms: int


ParseOutcome = ParseMealResult | ProviderCallError
CorrectionOutcome = ApplyCorrectionResult | ProviderCallError


class FakeReasoningModelProvider:
    """Script exact provider behaviour without opening a network connection."""

    def __init__(self) -> None:
        self._parse_outcomes: deque[ParseOutcome] = deque()
        self._correction_outcomes: deque[CorrectionOutcome] = deque()
        self.calls: list[FakeProviderCall] = []

    def queue_parse_result(
        self,
        value: ParsedMealDTO,
        *,
        usage: ProviderUsageDTO | None = None,
        latency_ms: int = 0,
        model_alias: str = "fake-reasoning-v1",
    ) -> None:
        self._parse_outcomes.append(
            ParseMealResult(
                value=value,
                metadata=_metadata(
                    usage=usage, latency_ms=latency_ms, model_alias=model_alias
                ),
            )
        )

    def queue_correction_result(
        self,
        value: CorrectionDTO,
        *,
        usage: ProviderUsageDTO | None = None,
        latency_ms: int = 0,
        model_alias: str = "fake-reasoning-v1",
    ) -> None:
        self._correction_outcomes.append(
            ApplyCorrectionResult(
                value=value,
                metadata=_metadata(
                    usage=usage, latency_ms=latency_ms, model_alias=model_alias
                ),
            )
        )

    def queue_parse_error(
        self, *, kind: ProviderFailureKind, code: str, safe_message: str | None = None
    ) -> None:
        self._parse_outcomes.append(
            ProviderCallError(
                kind=kind,
                code=code,
                safe_message=safe_message or "Scripted parse provider failure.",
            )
        )

    def queue_correction_error(
        self, *, kind: ProviderFailureKind, code: str, safe_message: str | None = None
    ) -> None:
        self._correction_outcomes.append(
            ProviderCallError(
                kind=kind,
                code=code,
                safe_message=safe_message or "Scripted correction provider failure.",
            )
        )

    async def parse_meal(self, request: ParseMealRequest) -> ParseMealResult:
        del request  # Input can contain meal text; trace storage must not retain it.
        outcome = _next_parse_outcome(self._parse_outcomes)
        self._record_call("parse_meal", outcome)
        if isinstance(outcome, ProviderCallError):
            raise outcome
        return outcome

    async def apply_correction(
        self, request: ApplyCorrectionRequest
    ) -> ApplyCorrectionResult:
        del request  # See parse_meal: only safe metadata is retained.
        outcome = _next_correction_outcome(self._correction_outcomes)
        self._record_call("apply_correction", outcome)
        if isinstance(outcome, ProviderCallError):
            raise outcome
        return outcome

    def _record_call(self, operation: str, outcome: ParseOutcome | CorrectionOutcome) -> None:
        metadata = outcome.metadata if not isinstance(outcome, ProviderCallError) else outcome.metadata
        metadata = metadata or _metadata()
        self.calls.append(
            FakeProviderCall(
                operation=operation,
                call_id=metadata.call_id,
                model_alias=metadata.model_alias,
                prompt_tokens=metadata.usage.prompt_tokens,
                completion_tokens=metadata.usage.completion_tokens,
                cost_usd=metadata.usage.cost_usd,
                latency_ms=metadata.latency_ms,
            )
        )


def _metadata(
    *,
    usage: ProviderUsageDTO | None = None,
    latency_ms: int = 0,
    model_alias: str = "fake-reasoning-v1",
) -> ProviderCallMetadataDTO:
    return ProviderCallMetadataDTO(
        model_alias=model_alias,
        usage=usage
        or ProviderUsageDTO(prompt_tokens=0, completion_tokens=0, cost_usd=Decimal("0")),
        latency_ms=latency_ms,
    )


def _next_parse_outcome(outcomes: deque[ParseOutcome]) -> ParseOutcome:
    if outcomes:
        return outcomes.popleft()
    return ProviderCallError(
        kind=ProviderFailureKind.PERMANENT,
        code="FAKE_UNSCRIPTED_CALL",
        safe_message="No scripted parse_meal outcome is available.",
    )


def _next_correction_outcome(outcomes: deque[CorrectionOutcome]) -> CorrectionOutcome:
    if outcomes:
        return outcomes.popleft()
    return ProviderCallError(
        kind=ProviderFailureKind.PERMANENT,
        code="FAKE_UNSCRIPTED_CALL",
        safe_message="No scripted apply_correction outcome is available.",
    )
