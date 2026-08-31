"""JSON-safe, bounded LangGraph state contracts for the meal-analysis graph."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


STATE_VERSION = "meal-agent-state.v2"
MAX_STATE_MESSAGES = 4
MAX_STATE_ITEMS = 20
MAX_STATE_CANDIDATES = 3


class AgentRuntimeStatus(StrEnum):
    ACCEPTED = "accepted"
    RUNNING = "running"
    WAITING_INPUT = "waiting_input"
    COMPLETED = "completed"
    FAILED = "failed"
    LIMIT_REACHED = "limit_reached"


class AgentNextAction(StrEnum):
    PARSE = "parse"
    VISION = "vision"
    RESOLVE_CATALOG = "resolve_catalog"
    ASK_USER = "ask_user"
    CALCULATE = "calculate"
    VALIDATE = "validate"
    REPORT = "report"
    STOP = "stop"


class AgentBudget(BaseModel):
    """Counters are state, while hard limits are configuration/runtime policy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    graph_steps: int = Field(default=0, ge=0, le=12)
    model_calls: int = Field(default=0, ge=0, le=4)
    tool_calls: int = Field(default=0, ge=0, le=12)
    active_elapsed_ms: int = Field(default=0, ge=0, le=45_000)
    estimated_cost_usd: Decimal = Field(default=Decimal("0"), ge=Decimal("0"), le=Decimal("0.02"))


class StateMealItem(BaseModel):
    """A model observation and tool-safe references, never an ORM row or provider DTO."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    item_id: str = Field(min_length=1, max_length=128)
    normalized_name: str = Field(min_length=1, max_length=200)
    grams: Decimal | None = Field(default=None, gt=Decimal("0"), le=Decimal("2000"))
    portion_description: str | None = Field(default=None, min_length=1, max_length=120)
    food_id: uuid.UUID | None = None
    catalog_version: str | None = Field(default=None, min_length=1, max_length=80)
    input_version: str = Field(min_length=1, max_length=80)
    is_dirty: bool = False
    search_query: str | None = Field(default=None, min_length=1, max_length=200)
    is_estimated: bool = False
    estimate_confidence: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))
    nutrients: "StateNutritionResult | None" = None


class StateImageReference(BaseModel):
    """The graph receives a short-lived opaque handle, never image bytes or upload metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    image_id: uuid.UUID
    digest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    mime_type: str = Field(pattern=r"^image/(?:jpeg|png|webp)$")
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    byte_size: int = Field(gt=0)
    locator: str = Field(pattern=r"^[a-f0-9]{32}\.(?:jpg|png|webp)$")
    created_at: datetime
    expires_at: datetime
    status: str = Field(pattern=r"^(?:ready|processing)$")


class StateVisionMetadata(BaseModel):
    """Allowlisted provider accounting; no prompt, raw response, or thought text is retained."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    model_alias: str = Field(min_length=1, max_length=128)
    provider_request_id: str | None = Field(default=None, min_length=1, max_length=128)
    image_tokens: int = Field(ge=0)
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    cost_cny: Decimal = Field(ge=Decimal("0"))
    latency_ms: int = Field(ge=0)
    prompt_version: str = Field(min_length=1, max_length=80)
    schema_version: str = Field(min_length=1, max_length=80)


class StateCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    item_id: str = Field(min_length=1, max_length=128)
    food_id: uuid.UUID
    catalog_version: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=240)


class StateNutritionResult(BaseModel):
    """Deterministic result already earned by an item; no model value is stored here."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    energy_kcal: Decimal
    protein_g: Decimal
    fat_g: Decimal
    carbohydrate_g: Decimal
    source_name: str = Field(min_length=1, max_length=120)
    source_url: str = Field(min_length=1, max_length=500)
    calculation_rule_version: str = Field(min_length=1, max_length=80)


class ClarificationQuestion(BaseModel):
    """JSON-safe, non-sensitive interrupt payload assembled after all deterministic work."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    item_id: str = Field(min_length=1, max_length=128)
    field: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=300)
    candidates: tuple[StateCandidate, ...] = Field(default=(), max_length=MAX_STATE_CANDIDATES)


class StateToolSummary(BaseModel):
    """Only stable action/version/digest summaries survive checkpoint persistence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_name: str = Field(min_length=1, max_length=80)
    tool_version: str = Field(min_length=1, max_length=80)
    action: str = Field(min_length=1, max_length=80)
    result_digest: str = Field(min_length=64, max_length=64)


class StateContextHint(BaseModel):
    """Only user-safe context survives checkpoints; IDs, vectors and retrieval scores do not."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: Literal["preference", "meal_history", "nutrition_knowledge"]
    summary: str = Field(min_length=1, max_length=500)


class MealAgentState(BaseModel):
    """Versioned State passed between graph nodes and serialized by the checkpointer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    state_version: str = STATE_VERSION
    user_id: uuid.UUID
    thread_id: uuid.UUID
    run_id: uuid.UUID
    messages: tuple[str, ...] = Field(default=(), max_length=MAX_STATE_MESSAGES)
    conversation_summary: str = Field(default="", max_length=2_000)
    items: tuple[StateMealItem, ...] = Field(default=(), max_length=MAX_STATE_ITEMS)
    missing_fields: tuple[str, ...] = Field(default=(), max_length=MAX_STATE_ITEMS)
    candidates: tuple[StateCandidate, ...] = Field(default=(), max_length=MAX_STATE_CANDIDATES)
    clarification_questions: tuple[ClarificationQuestion, ...] = Field(
        default=(), max_length=MAX_STATE_ITEMS
    )
    unaccounted_items: tuple[str, ...] = Field(default=(), max_length=MAX_STATE_ITEMS)
    is_partial: bool = False
    tool_summaries: tuple[StateToolSummary, ...] = Field(default=(), max_length=36)
    context_hints: tuple[StateContextHint, ...] = Field(default=(), max_length=9)
    validation_issues: tuple[str, ...] = Field(default=(), max_length=MAX_STATE_ITEMS)
    dirty_item_ids: tuple[str, ...] = Field(default=(), max_length=MAX_STATE_ITEMS)
    budget: AgentBudget = Field(default_factory=AgentBudget)
    next_action: AgentNextAction = AgentNextAction.PARSE
    report: dict[str, object] | None = None
    graph_version: str = Field(min_length=1, max_length=80)
    prompt_version: str = Field(min_length=1, max_length=80)
    tool_version: str = Field(min_length=1, max_length=80)
    model_version: str | None = Field(default=None, min_length=1, max_length=120)
    status: AgentRuntimeStatus = AgentRuntimeStatus.ACCEPTED
    vision_image: StateImageReference | None = None
    vision_metadata: StateVisionMetadata | None = None
    vision_request_key: str | None = Field(default=None, min_length=1, max_length=128)
    vision_invocation_status: str | None = Field(
        default=None, pattern=r"^(?:prepared|completed|failed|outcome_unknown)$"
    )
    vision_attempts: int = Field(default=0, ge=0, le=2)
    image_refs: tuple[()] = ()

    @model_validator(mode="after")
    def requires_unique_items_and_forbids_phase_two_images(self) -> MealAgentState:
        item_ids = [item.item_id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("state item ids must be unique")
        if self.image_refs:
            raise ValueError("legacy image_refs cannot retain image references")
        if self.next_action is AgentNextAction.VISION and self.vision_image is None:
            raise ValueError("vision action requires a validated image reference")
        if self.status is AgentRuntimeStatus.COMPLETED and self.report is None:
            raise ValueError("completed state requires a report")
        return self
