"""JSON-safe, bounded LangGraph state contracts for the meal-analysis graph."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.planning.schemas import DailyTarget, MealSlot, PlannedMeal, PlanningProfileInput, PreferenceReview


STATE_VERSION = "meal-agent-state.v3"
DIET_PLANNING_STATE_VERSION = "diet-planning-state.v1"
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


class AgentGraphKind(StrEnum):
    """A checkpoint namespace is selected from a closed graph kind, never client input."""

    MEAL_ANALYSIS = "meal_analysis"
    DIET_PLANNING = "diet_planning"


class DietPlanningAction(StrEnum):
    READ_CONTEXT = "reading_context"
    CALCULATE_TARGETS = "calculating_targets"
    COMPOSE_PLAN = "composing_plan"
    VALIDATE_PLAN = "validating_plan"
    COMPLETE = "complete"
    NEEDS_INPUT = "needs_input"


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
    """Safe, explainable catalog projection persisted in a checkpoint.

    Retrieval evidence is intentionally not state: rank, score, vector, query and provider
    payloads are ephemeral inputs to deterministic search, not durable graph facts.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    item_id: str = Field(min_length=1, max_length=128)
    food_id: uuid.UUID
    catalog_version: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=240)
    canonical_label: str | None = Field(default=None, min_length=1, max_length=240)
    relation_label: str | None = Field(default=None, min_length=1, max_length=80)
    prepared_state: str | None = Field(default=None, min_length=1, max_length=120)
    portion_hints: tuple[Annotated[str, Field(min_length=1, max_length=120)], ...] = Field(
        default=(), max_length=3
    )
    source_name: str | None = Field(default=None, min_length=1, max_length=120)


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
    # This is deliberately only a completion marker.  A checkpoint must not retain the source
    # sentence, provider request key, ledger identifier, or any provider response for a write.
    explicit_preference_capture_completed: bool = False
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

class StateRecipeCandidate(BaseModel):
    """Version-bound recipe offer, separate from domain and provider DTOs."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    recipe_id: uuid.UUID
    revision: int = Field(ge=1)
    food_id: uuid.UUID
    catalog_version: str = Field(min_length=1, max_length=80)
    display_name: str = Field(min_length=1, max_length=200)
    meal_slot: MealSlot
    portion_grams: Decimal = Field(gt=0, le=Decimal("2000"))
    portion_description: str = Field(min_length=1, max_length=120)
    method_tags: tuple[str, ...]
    flavour_tags: tuple[str, ...]


class DietPlanningState(BaseModel):
    """Planning-only checkpoint state with no meal-analysis/provider fields.

    Keeping this state separate is a security boundary: a meal checkpoint can never be decoded
    as a planning command, and planning's profile snapshot cannot leak into meal execution.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    state_version: Literal["diet-planning-state.v1"] = "diet-planning-state.v1"
    graph_kind: Literal["diet_planning"] = "diet_planning"
    user_id: uuid.UUID
    thread_id: uuid.UUID
    run_id: uuid.UUID
    command_key: str = Field(min_length=1, max_length=128)
    profile: "PlanningProfileInput"
    preferences: "PreferenceReview"
    save_profile: bool = False
    profile_save_completed: bool = False
    target: "DailyTarget | None" = None
    meals: tuple["PlannedMeal", ...] = Field(default=(), max_length=3)
    replan_count: int = Field(default=0, ge=0, le=3)
    # Opaque hashes make capture replay-safe without retaining the user's freeform feedback.
    preference_capture_markers: tuple[str, ...] = Field(default=(), max_length=3)
    pending_adjustment_intent: Literal["lighter", "replace"] | None = None
    pending_adjustment_slot: "MealSlot | None" = None
    pending_food_query: str | None = Field(default=None, min_length=1, max_length=200)
    pending_food_candidates: tuple[StateCandidate, ...] = Field(default=(), max_length=MAX_STATE_CANDIDATES)
    pending_recipe_candidates: tuple[StateRecipeCandidate, ...] = Field(default=(), max_length=20)
    tool_summaries: tuple[StateToolSummary, ...] = Field(default=(), max_length=12)
    budget: AgentBudget = Field(default_factory=AgentBudget)
    next_action: DietPlanningAction = DietPlanningAction.READ_CONTEXT
    status: AgentRuntimeStatus = AgentRuntimeStatus.ACCEPTED
    report: dict[str, object] | None = None
    graph_version: str = Field(min_length=1, max_length=80)
    prompt_version: str = Field(min_length=1, max_length=80)
    tool_version: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def keeps_three_slots_and_terminal_reports_unambiguous(self) -> "DietPlanningState":
        if self.meals and len({meal.slot for meal in self.meals}) != len(self.meals):
            raise ValueError("planning meal slots must be unique")
        if self.status is AgentRuntimeStatus.COMPLETED:
            if self.report is None or len(self.meals) != 3:
                raise ValueError("completed planning state requires a three-meal report")
        return self
