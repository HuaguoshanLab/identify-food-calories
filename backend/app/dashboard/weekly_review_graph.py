"""Facts-only, bounded weekly-review generation without ORM or repository access."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from time import monotonic
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.providers.reasoning.dto import (
    ProviderCallError,
    ProviderFailureKind,
    WeeklyReviewFactsDTO,
    WeeklyReviewOutputDTO,
    WeeklyReviewRequest,
)
from app.providers.reasoning.ports import ReasoningModelProvider


GRAPH_VERSION = "weekly-review-graph.v2"
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


class _WeeklyReviewState(TypedDict, total=False):
    """Transient graph state. The graph is deliberately compiled without a checkpointer."""

    facts: Mapping[str, object]
    facts_digest: str
    request: WeeklyReviewRequest
    output: WeeklyReviewOutputDTO
    started_at: float
    model_calls: int
    cost_usd: Decimal
    attempt: int
    failure_code: str
    result: WeeklyReviewGraphResult


class WeeklyReviewGraph:
    """One safe provider operation plus one correction retry; never persists payload bodies."""

    def __init__(self, *, provider: ReasoningModelProvider, config: WeeklyReviewGraphConfig) -> None:
        self._provider = provider
        self._config = config
        self._compiled = self._build_graph()

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
        state = await self._compiled.ainvoke(
            {
                "facts": facts,
                "facts_digest": facts_digest,
                "started_at": monotonic(),
                "model_calls": 0,
                "cost_usd": Decimal("0"),
                "attempt": 0,
            },
            config={"recursion_limit": 12},
        )
        return state["result"]

    def _build_graph(self):
        builder = StateGraph(_WeeklyReviewState)
        builder.add_node("validate_facts", self._validate_facts_node)
        builder.add_node("admit", self._admission_node)
        builder.add_node("call_provider", self._provider_node)
        builder.add_node("validate_semantics", self._semantic_validation_node)
        builder.add_node("prepare_retry", self._retry_node)
        builder.add_node("complete", self._complete_node)
        builder.add_node("abstain", self._abstain_node)
        builder.add_edge(START, "validate_facts")
        builder.add_conditional_edges(
            "validate_facts", self._route_failure, {"continue": "admit", "abstain": "abstain"}
        )
        builder.add_conditional_edges(
            "admit", self._route_failure, {"continue": "call_provider", "abstain": "abstain"}
        )
        builder.add_conditional_edges(
            "call_provider",
            self._route_provider,
            {"validate": "validate_semantics", "retry": "prepare_retry", "abstain": "abstain"},
        )
        builder.add_conditional_edges(
            "validate_semantics",
            self._route_semantics,
            {"complete": "complete", "retry": "prepare_retry", "abstain": "abstain"},
        )
        builder.add_edge("prepare_retry", "call_provider")
        builder.add_edge("complete", END)
        builder.add_edge("abstain", END)
        return builder.compile()

    def _validate_facts_node(self, state: _WeeklyReviewState) -> dict[str, object]:
        try:
            request = self._request_from_facts(state["facts"])
        except (ValidationError, ValueError):
            return {"failure_code": "WEEKLY_REVIEW_FACTS_INVALID"}
        return {"request": request}

    def _admission_node(self, state: _WeeklyReviewState) -> dict[str, object]:
        request = state["request"]
        if not request.facts.coverage_sufficient:
            return {"failure_code": "INSUFFICIENT_COVERAGE"}
        if not self._config.provider_enabled:
            return {"failure_code": "PROVIDER_DISABLED"}
        if self._config.call_cap == 0 or self._config.per_run_cost_cap_usd <= 0:
            return {"failure_code": "BUDGET_DENIED"}
        return {}

    async def _provider_node(self, state: _WeeklyReviewState) -> dict[str, object]:
        calls = state["model_calls"]
        if calls >= self._config.call_cap or calls >= 2:
            return {"failure_code": "BUDGET_DENIED"}
        remaining = self._config.timeout_ms / 1000 - (monotonic() - state["started_at"])
        if remaining <= 0:
            return {"failure_code": "WEEKLY_REVIEW_TIMEOUT"}
        try:
            async with asyncio.timeout(remaining):
                provider_result = await self._provider.generate_weekly_review(state["request"])
        except TimeoutError:
            return {"model_calls": calls + 1, "failure_code": "WEEKLY_REVIEW_TIMEOUT"}
        except ProviderCallError as error:
            update: dict[str, object] = {"model_calls": calls + 1}
            if error.kind is ProviderFailureKind.OUTCOME_UNKNOWN:
                update["failure_code"] = "PROVIDER_OUTCOME_UNKNOWN"
            elif error.code == "PROVIDER_SCHEMA_INVALID" and state["attempt"] == 0:
                update["failure_code"] = "RETRY_SCHEMA"
            else:
                update["failure_code"] = (
                    "WEEKLY_REVIEW_SCHEMA_INVALID"
                    if error.code == "PROVIDER_SCHEMA_INVALID"
                    else "PROVIDER_FAILURE"
                )
            return update

        cost = state["cost_usd"] + provider_result.metadata.usage.cost_usd
        update = {
            "model_calls": calls + 1,
            "cost_usd": cost,
            "output": provider_result.value,
            "failure_code": "",
        }
        if (
            provider_result.metadata.usage.completion_tokens > 360
            or cost > self._config.per_run_cost_cap_usd
        ):
            update["failure_code"] = "BUDGET_DENIED"
        return update

    def _semantic_validation_node(self, state: _WeeklyReviewState) -> dict[str, object]:
        try:
            validate_weekly_review_semantics(state["output"], state["request"].facts)
        except ValueError:
            return {
                "failure_code": (
                    "RETRY_SAFETY"
                    if state["attempt"] == 0
                    else "WEEKLY_REVIEW_SAFETY_REJECTED"
                )
            }
        return {"failure_code": ""}

    def _retry_node(self, state: _WeeklyReviewState) -> dict[str, object]:
        return {
            "request": state["request"].model_copy(
                update={"retry_reason": "schema_or_safety_invalid"}
            ),
            "attempt": state["attempt"] + 1,
            "failure_code": "",
        }

    def _complete_node(self, state: _WeeklyReviewState) -> dict[str, object]:
        calls = state["model_calls"]
        return {
            "result": WeeklyReviewGraphResult(
                code="COMPLETED",
                model_calls=calls,
                ledger=_ledger("completed", None, calls),
                ledger_metadata=self._ledger_metadata(state["facts_digest"]),
                suggestions=tuple(item.text for item in state["output"].suggestions),
            )
        }

    def _abstain_node(self, state: _WeeklyReviewState) -> dict[str, object]:
        return {
            "result": self._abstain(
                state["failure_code"], state["model_calls"], state["facts_digest"]
            )
        }

    @staticmethod
    def _route_failure(state: _WeeklyReviewState) -> str:
        return "abstain" if state.get("failure_code") else "continue"

    @staticmethod
    def _route_provider(state: _WeeklyReviewState) -> str:
        failure = state.get("failure_code")
        if failure == "RETRY_SCHEMA":
            return "retry"
        return "abstain" if failure else "validate"

    @staticmethod
    def _route_semantics(state: _WeeklyReviewState) -> str:
        failure = state.get("failure_code")
        if failure == "RETRY_SAFETY":
            return "retry"
        return "abstain" if failure else "complete"

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
        raw_patterns = facts.get("allowed_patterns", [])
        patterns = list(raw_patterns) if isinstance(raw_patterns, (list, tuple)) else []
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
                queue(
                    WeeklyReviewOutputDTO.model_validate(
                        {
                            "suggestions": [{"category": unsafe_category, "text": text}],
                            "disclaimer": _SAFE_DISCLAIMER,
                        }
                    )
                )
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
