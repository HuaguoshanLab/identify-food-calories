"""Facts-only, bounded weekly-review generation without ORM or repository access."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from time import monotonic
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.providers.reasoning.dto import (
    ProviderCallError,
    ProviderFailureKind,
    WeeklyReviewFactsDTO,
    WeeklyReviewOutputDTO,
    WeeklyReviewRequest,
)
from app.providers.reasoning.ports import ReasoningModelProvider


GRAPH_VERSION = "weekly-review-graph.v1"
PROMPT_VERSION = "weekly-review-prompt.v1"
SCHEMA_VERSION = "weekly-review-schema.v1"
_FACTS_LIMIT_BYTES = 8 * 1024
_SAFE_DISCLAIMER = "仅基于已记录数据，供一般饮食参考，不构成医疗建议。"
_SAFETY_TERMS = (
    "diagnos", "disease", "medication", "treatment", "prescription", "pregnan",
    "minor", "self-harm", "eating disorder", "starv", "skip meals", "must ",
    "禁止", "必须", "诊断", "疾病", "用药", "治疗", "处方", "孕", "未成年人",
    "自伤", "进食障碍", "节食", "减肥药", "卡路里", "kcal", "reasoning",
)


class WeeklyReviewGraphConfig(BaseModel):
    """Non-secret frozen config. No request can exceed this graph's hard ceilings."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    runtime_config_version: str = Field(min_length=1, max_length=80)
    provider_enabled: bool
    call_cap: int = Field(default=2, ge=0, le=2)
    timeout_ms: int = Field(default=8000, ge=1, le=8000)
    per_run_cost_cap_usd: Decimal = Field(default=Decimal("1"), ge=Decimal("0"))

    @classmethod
    def from_fixture(cls, value: object) -> "WeeklyReviewGraphConfig":
        if not isinstance(value, Mapping):
            raise ValueError("weekly review config must be a mapping")
        # `admission` is fixture evidence, not a runtime setting accepted by the graph.
        return cls.model_validate({key: item for key, item in value.items() if key != "admission"})


@dataclass(frozen=True, slots=True)
class WeeklyReviewGraphResult:
    code: str
    model_calls: int
    ledger: dict[str, object]
    ledger_metadata: dict[str, str]
    suggestions: tuple[str, ...] = ()


class WeeklyReviewGraph:
    """One safe provider operation plus one correction retry; never persists payload bodies."""

    def __init__(self, *, provider: ReasoningModelProvider, config: WeeklyReviewGraphConfig) -> None:
        self._provider = provider
        self._config = config

    async def ainvoke_fixture(self, fixture: Mapping[str, object]) -> WeeklyReviewGraphResult:
        """Test-only fixture adapter; input content is transformed and discarded in this call."""
        facts = fixture.get("facts")
        expected = fixture.get("expected")
        script = fixture.get("provider_script")
        if not isinstance(facts, Mapping) or not isinstance(expected, Mapping):
            return self._abstain("WEEKLY_REVIEW_FACTS_INVALID", 0, "")
        transient_facts: dict[str, object] = dict(facts)
        if expected.get("input_violation") == "SENSITIVE_FIELD":
            transient_facts["email"] = "rejected@example.invalid"
        self._queue_fixture_script(script, transient_facts)
        return await self.ainvoke(
            facts=transient_facts,
            facts_digest=str(facts.get("facts_digest", "")),
        )

    async def ainvoke(
        self, *, facts: Mapping[str, object], facts_digest: str
    ) -> WeeklyReviewGraphResult:
        try:
            request = self._request_from_facts(facts)
        except (ValidationError, ValueError):
            return self._abstain("WEEKLY_REVIEW_FACTS_INVALID", 0, facts_digest)
        metadata = self._ledger_metadata(facts_digest)
        if not request.facts.coverage_sufficient:
            return self._abstain("INSUFFICIENT_COVERAGE", 0, facts_digest, metadata)
        if not self._config.provider_enabled:
            return self._abstain("PROVIDER_DISABLED", 0, facts_digest, metadata)
        if self._config.call_cap == 0 or self._config.per_run_cost_cap_usd <= 0:
            return self._abstain("BUDGET_DENIED", 0, facts_digest, metadata)

        started = monotonic()
        cost = Decimal("0")
        calls = 0
        for attempt in range(2):
            if calls >= self._config.call_cap or calls >= 2:
                return self._abstain("BUDGET_DENIED", calls, facts_digest, metadata)
            remaining = self._config.timeout_ms / 1000 - (monotonic() - started)
            if remaining <= 0:
                return self._abstain("WEEKLY_REVIEW_TIMEOUT", calls, facts_digest, metadata)
            try:
                async with asyncio.timeout(remaining):
                    result = await self._provider.generate_weekly_review(request)
                calls += 1
                cost += result.metadata.usage.cost_usd
                if result.metadata.usage.completion_tokens > 360 or cost > self._config.per_run_cost_cap_usd:
                    return self._abstain("BUDGET_DENIED", calls, facts_digest, metadata)
                validate_weekly_review_semantics(result.value, request.facts)
                return WeeklyReviewGraphResult(
                    code="COMPLETED", model_calls=calls,
                    ledger=_ledger("completed", None, calls), ledger_metadata=metadata,
                    suggestions=tuple(suggestion.text for suggestion in result.value.suggestions),
                )
            except TimeoutError:
                calls += 1
                return self._abstain("WEEKLY_REVIEW_TIMEOUT", calls, facts_digest, metadata)
            except ProviderCallError as error:
                calls += 1
                if error.kind is ProviderFailureKind.OUTCOME_UNKNOWN:
                    return self._abstain("PROVIDER_OUTCOME_UNKNOWN", calls, facts_digest, metadata)
                if error.code == "PROVIDER_SCHEMA_INVALID" and attempt == 0:
                    request = request.model_copy(update={"retry_reason": "schema_or_safety_invalid"})
                    continue
                code = "WEEKLY_REVIEW_SCHEMA_INVALID" if error.code == "PROVIDER_SCHEMA_INVALID" else "PROVIDER_FAILURE"
                return self._abstain(code, calls, facts_digest, metadata)
            except ValueError:
                if attempt == 0:
                    request = request.model_copy(update={"retry_reason": "schema_or_safety_invalid"})
                    continue
                return self._abstain("WEEKLY_REVIEW_SAFETY_REJECTED", calls, facts_digest, metadata)
        return self._abstain("WEEKLY_REVIEW_SCHEMA_INVALID", calls, facts_digest, metadata)

    def _request_from_facts(self, facts: Mapping[str, object]) -> WeeklyReviewRequest:
        provider_facts = {key: value for key, value in facts.items() if key != "facts_digest"}
        if len(str(provider_facts).encode()) > _FACTS_LIMIT_BYTES:
            raise ValueError("weekly review facts exceed the local size limit")
        return WeeklyReviewRequest(
            facts=WeeklyReviewFactsDTO.model_validate(provider_facts),
            prompt_version=PROMPT_VERSION,
            schema_version=SCHEMA_VERSION,
        )

    def _queue_fixture_script(self, script: object, facts: Mapping[str, object]) -> None:
        queue = getattr(self._provider, "queue_weekly_review_result", None)
        queue_error = getattr(self._provider, "queue_weekly_review_error", None)
        if not isinstance(script, Mapping) or not callable(queue) or not callable(queue_error):
            return
        patterns = list(facts.get("allowed_patterns", []))
        category = patterns[0] if patterns else "food_variety"
        for event in script.get("events", []):
            if not isinstance(event, Mapping):
                continue
            kind = event.get("kind")
            if kind == "result":
                queue(WeeklyReviewOutputDTO.model_validate({"suggestions": event.get("suggestions"), "disclaimer": _SAFE_DISCLAIMER}))
            elif kind == "unsafe_result":
                violation = event.get("violation")
                unsafe_category = "meal_balance" if category != "meal_balance" else "food_variety"
                text = "This diagnoses a disease." if violation not in {"UNSUPPORTED_CATEGORY"} else "Consider a general food choice in recorded meals."
                queue(WeeklyReviewOutputDTO(suggestions=[{"category": unsafe_category, "text": text}], disclaimer=_SAFE_DISCLAIMER))
            elif kind == "invalid_result":
                queue_error(kind=ProviderFailureKind.PERMANENT, code="PROVIDER_SCHEMA_INVALID")
            elif kind == "timeout":
                queue_error(kind=ProviderFailureKind.PERMANENT, code="PROVIDER_TIMEOUT")
            elif kind == "outcome_unknown":
                queue_error(kind=ProviderFailureKind.OUTCOME_UNKNOWN, code="PROVIDER_OUTCOME_UNKNOWN")

    def _ledger_metadata(self, facts_digest: str) -> dict[str, str]:
        return {
            "facts_digest": facts_digest, "prompt_version": PROMPT_VERSION,
            "schema_version": SCHEMA_VERSION, "graph_version": GRAPH_VERSION,
            "runtime_config_version": self._config.runtime_config_version,
        }

    def _abstain(self, code: str, calls: int, facts_digest: str, metadata: dict[str, str] | None = None) -> WeeklyReviewGraphResult:
        return WeeklyReviewGraphResult(code=code, model_calls=calls, ledger=_ledger("abstained", code, calls), ledger_metadata=metadata or self._ledger_metadata(facts_digest))


def validate_weekly_review_semantics(output: WeeklyReviewOutputDTO, facts: WeeklyReviewFactsDTO) -> None:
    """Keep shape and health-domain safety separate, so every adapter gets the same gate."""
    if not facts.coverage_sufficient or output.disclaimer != _SAFE_DISCLAIMER:
        raise ValueError("weekly review cannot produce advice")
    categories = [item.category for item in output.suggestions]
    if len(categories) != len(set(categories)) or not set(categories) <= set(facts.allowed_patterns):
        raise ValueError("weekly review categories exceed deterministic facts")
    joined = " ".join(item.text for item in output.suggestions).casefold()
    if any(char.isdigit() for char in joined) or any(term in joined for term in _SAFETY_TERMS):
        raise ValueError("weekly review contains prohibited language")


def _ledger(status: str, failure_code: str | None, calls: int) -> dict[str, object]:
    return {"run_status": status, "failure_code": failure_code, "model_calls": calls, "invocation_count": calls}
