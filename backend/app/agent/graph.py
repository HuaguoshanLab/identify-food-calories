"""Pure main-graph routing and lifespan contracts.

This module intentionally contains no SQLAlchemy, ORM or repository import.  A
runtime built in later plans injects a `NutritionToolAdapter` and a persisted
checkpointer after AgentService has already proved thread ownership.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from collections.abc import Callable

from app.agent.state import (
    AgentNextAction,
    AgentRuntimeStatus,
    ClarificationQuestion,
    MealAgentState,
    StateMealItem,
    StateNutritionResult,
    StateToolSummary,
    StateContextHint,
    StateCandidate,
    StateVisionMetadata,
    DietPlanningAction,
    DietPlanningState,
)
from app.agent.tools import NutritionToolAdapter, PlanningToolAdapter
from app.planning.schemas import DailyTarget, MealSlot, PlanValidationAction, PlannedMeal, PreferenceReview
from app.images.schemas import ValidatedImageReference
from app.nutrition.schemas import (
    FoodSearchInput,
    FoodSearchCandidate,
    NutritionCalculationInput,
    NutritionValidationInput,
    QualifiedFood,
)
from app.providers.reasoning.dto import (
    ParseMealRequest,
    ParseMealResult,
    ProviderCallError,
    ProviderFailureKind,
)
from app.providers.reasoning.ports import ReasoningModelProvider
from app.providers.vision.dto import VisionMealRequest, VisionMealResult
from app.providers.vision.ports import VisionModelProvider
from app.agent.runtime_errors import AgentRuntimeStageError


GRAPH_VERSION = "meal-agent-graph.v1"
LOGGER = logging.getLogger(__name__)
_EXPLICIT_GRAMS = re.compile(
    r"(?<![\d.])(\d+(?:\.\d+)?)\s*(?:g(?![A-Za-z])|克)", re.IGNORECASE
)


class AgentIntent(StrEnum):
    MEAL_ANALYSIS = "MEAL_ANALYSIS"
    DIET_PLANNING = "DIET_PLANNING"


class GraphRoute(StrEnum):
    MEAL_ANALYSIS = "MEAL_ANALYSIS"
    DIET_PLANNING = "DIET_PLANNING"


class AgentGraph(Protocol):
    """Compiled graph facade used by HTTP/supervisor lifecycles in later plans."""

    async def ainvoke(
        self, state: MealAgentState | DietPlanningState, *, resume: dict[str, object] | None = None
    ) -> MealAgentState | DietPlanningState: ...


@dataclass(frozen=True, slots=True)
class AgentRuntime:
    """Long-lived runtime dependencies created once by FastAPI lifespan."""

    graph: AgentGraph
    tools: NutritionToolAdapter
    checkpointer: object
    supervisor: object
    session_factory: Callable[[], object]
    image_safety: object


class AgentRuntimeFactory(Protocol):
    """Lifecycle seam: create once at startup, never per request or graph node."""

    async def create(self) -> AgentRuntime | None: ...

    async def close(self, runtime: AgentRuntime | None) -> None: ...


class NoopAgentRuntimeFactory:
    """Explicit temporary lifecycle owner until the persisted runtime is wired."""

    async def create(self) -> AgentRuntime | None:
        return None

    async def close(self, runtime: AgentRuntime | None) -> None:
        _ = runtime


def _digest(value: object) -> str:
    """Checkpoint state records only deterministic result digests, never provider text."""

    return hashlib.sha256(repr(value).encode("utf-8")).hexdigest()


class MealAnalysisGraph:
    """Bounded meal graph using a provider observation and deterministic nutrition tools.

    The object deliberately knows nothing about SQLAlchemy, AgentService or HTTP.  Its caller
    has already written the run ledger and proved tenant ownership before invoking it.
    """

    def __init__(
        self,
        *,
        provider: ReasoningModelProvider,
        tools: NutritionToolAdapter,
        vision_provider: VisionModelProvider | None = None,
        vision_model_alias: str = "fake-vision-v1",
        vision_pixel_budget: int = 20_000_000,
        monotonic_ms: Callable[[], int] | None = None,
    ) -> None:
        self._provider = provider
        self._tools = tools
        self._vision_provider = vision_provider
        self._vision_model_alias = vision_model_alias
        if vision_pixel_budget <= 0 or vision_pixel_budget > 20_000_000:
            raise ValueError("vision pixel budget is invalid")
        self._vision_pixel_budget = vision_pixel_budget
        self._monotonic_ms = monotonic_ms or _monotonic_ms

    async def ainvoke(
        self, state: MealAgentState, *, resume: dict[str, object] | None = None
    ) -> MealAgentState:
        """Advance a pure state machine; the service owns persistence and idempotency.

        A waiting state never calls the provider again.  The previous parse/search work is
        already in the checkpoint, so an invalid resume is a no-op and a valid answer only marks
        the affected item dirty before deterministic tools are called again.
        """

        started_ms = self._monotonic_ms()
        state = self._capture_fresh_text_preferences(state)
        if state.status is AgentRuntimeStatus.LIMIT_REACHED:
            return state
        if state.messages and not state.context_hints:
            retrieve_context = getattr(self._tools, "retrieve_personal_context", None)
            if callable(retrieve_context):
                # Context is optional guidance and is deliberately collected before parsing. It
                # cannot alter the deterministic Nutrition Service calls below.
                try:
                    hints = retrieve_context(user_id=state.user_id, query=state.messages[-1])
                except Exception as error:
                    raise AgentRuntimeStageError.from_exception(
                        stage="context_retrieval", error=error
                    ) from None
                state = state.model_copy(
                    update={
                        "context_hints": tuple(
                            StateContextHint(source=hint.source, summary=hint.summary)
                            for hint in hints[:9]
                        )
                    }
                )
        resumed = False
        # Invalid/no-answer resumes are a no-op, not a graph transition.  Charging a new step
        # here would make a client typo consume the autonomous-work budget.
        if state.next_action is AgentNextAction.ASK_USER:
            if resume is None:
                return state
            preview = self._apply_resume(state, resume)
            if preview is state:
                return state
            state = preview
            resumed = True
        elif state.next_action is AgentNextAction.REPORT:
            if resume is None:
                return state
            preview = self._apply_correction(state, resume)
            if preview is state:
                return state
            state = preview
            resumed = True
        if state.next_action is AgentNextAction.VISION:
            state = _begin_transition(state)
            if state.status is AgentRuntimeStatus.LIMIT_REACHED:
                return state
            observed = await self._observe_image(state)
            if observed.status is not AgentRuntimeStatus.ACCEPTED:
                return self._finish_transition(observed, started_ms)
            return self._finish_transition(await self._resolve(observed), started_ms)
        state = _begin_transition(state)
        if state.status is AgentRuntimeStatus.LIMIT_REACHED:
            return state
        if resumed:
            return self._finish_transition(await self._resolve(state), started_ms)
        if state.next_action is AgentNextAction.ASK_USER:
            result = await self._resolve(state)
            return self._finish_transition(result, started_ms)
        if state.next_action is AgentNextAction.REPORT:
            result = await self._resolve(state)
            return self._finish_transition(result, started_ms)
        if state.next_action is not AgentNextAction.PARSE or len(state.messages) != 1:
            return self._finish_transition(state.model_copy(
                update={"status": AgentRuntimeStatus.FAILED, "next_action": AgentNextAction.STOP}
            ), started_ms)
        parsed, parsed_state = await self._parse_with_one_transient_retry(state)
        if parsed is None:
            return self._finish_transition(parsed_state, started_ms)
        items = tuple(
            StateMealItem(
                item_id=item.item_id,
                normalized_name=item.food_name,
                grams=item.grams,
                portion_description=item.quantity_text,
                input_version="v1",
                is_dirty=True,
                search_query=item.catalog_query or item.food_name,
            )
            for item in parsed.value.items
        )
        recovered_grams = _recover_single_explicit_grams(
            message=state.messages[0], items=items
        )
        if recovered_grams is not None:
            item_id, grams = recovered_grams
            items = tuple(
                item.model_copy(update={"grams": grams}) if item.item_id == item_id else item
                for item in items
            )
        recovered_portion = _recover_single_portion_description(
            message=state.messages[0], items=items
        )
        if recovered_portion is not None:
            item_id, portion_description = recovered_portion
            items = tuple(
                item.model_copy(update={"portion_description": portion_description})
                if item.item_id == item_id
                else item
                for item in items
            )
        missing = tuple(
            f"{field.item_id}:{field.field}"
            for field in parsed.value.missing_fields
            if recovered_grams is None
            or field.item_id != recovered_grams[0]
            or field.field != "grams"
        )
        return self._finish_transition(await self._resolve(
            parsed_state.model_copy(update={"items": items, "messages": (), "missing_fields": missing})
        ), started_ms)

    def _capture_fresh_text_preferences(self, state: MealAgentState) -> MealAgentState:
        """Persist deterministic first-person preferences once through the graph's narrow port."""

        if (
            state.explicit_preference_capture_completed
            or state.next_action is not AgentNextAction.PARSE
            or state.status is not AgentRuntimeStatus.ACCEPTED
            or len(state.messages) != 1
        ):
            return state
        capture = getattr(self._tools, "capture_explicit_preferences", None)
        if not callable(capture):
            return state
        if state.budget.tool_calls >= 12:
            return _limit_state(state)
        try:
            captured = capture(
                user_id=state.user_id,
                run_id=state.run_id,
                statement=state.messages[0],
            )
        except Exception as error:
            raise AgentRuntimeStageError.from_exception(
                stage="preference_capture", error=error
            ) from None
        safe_result = tuple((item.category, item.canonical_text) for item in captured)
        return state.model_copy(
            update={
                "explicit_preference_capture_completed": True,
                "tool_summaries": (*state.tool_summaries, StateToolSummary(
                    tool_name="capture_explicit_preferences",
                    tool_version="memory-direct-capture.v1",
                    action="captured" if safe_result else "no_match",
                    result_digest=_digest(safe_result),
                )),
                "budget": state.budget.model_copy(update={"tool_calls": state.budget.tool_calls + 1}),
            }
        )

    async def _observe_image(self, state: MealAgentState) -> MealAgentState:
        """Use the Vision port with one classified transient retry and safe state only."""

        image = state.vision_image
        if image is None or state.vision_invocation_status == "outcome_unknown":
            return state.model_copy(
                update={"status": AgentRuntimeStatus.FAILED, "next_action": AgentNextAction.STOP}
            )
        if state.vision_invocation_status == "completed":
            return state.model_copy(update={"next_action": AgentNextAction.RESOLVE_CATALOG})
        if self._vision_provider is None:
            return state.model_copy(
                update={"status": AgentRuntimeStatus.FAILED, "next_action": AgentNextAction.STOP}
            )
        reference = ValidatedImageReference(
            digest_sha256=image.digest_sha256,
            mime_type=image.mime_type,  # type: ignore[arg-type]
            width=image.width,
            height=image.height,
            byte_size=image.byte_size,
            locator=image.locator,
            created_at=image.created_at,
            expires_at=image.expires_at,
        )
        request = VisionMealRequest(
            image=reference,
            model_alias=self._vision_model_alias,
            pixel_budget=self._vision_pixel_budget,
            request_key=state.vision_request_key or f"{state.run_id.hex}-{image.image_id.hex}",
        )
        attempts = state.vision_attempts
        for _ in range(2 - attempts):
            attempts += 1
            try:
                observed = await self._vision_provider.analyze_meal_image(request)
            except ProviderCallError as error:
                # The provider envelope is intentionally safe: log only its stable category and
                # code, never the image, authorization header, vendor body, or model reasoning.
                LOGGER.warning(
                    "vision_provider_failed kind=%s code=%s",
                    error.kind.value,
                    error.code,
                )
                if error.kind is ProviderFailureKind.TRANSIENT and attempts < 2:
                    continue
                invocation_status = (
                    "outcome_unknown"
                    if error.kind is ProviderFailureKind.OUTCOME_UNKNOWN
                    else "failed"
                )
                return state.model_copy(
                    update={
                        "vision_attempts": attempts,
                        "vision_invocation_status": invocation_status,
                        "status": AgentRuntimeStatus.FAILED,
                        "next_action": AgentNextAction.STOP,
                    }
                )
            return _vision_result_state(state.model_copy(update={"vision_attempts": attempts}), observed)
        return state.model_copy(
            update={
                "vision_attempts": attempts,
                "vision_invocation_status": "failed",
                "status": AgentRuntimeStatus.FAILED,
                "next_action": AgentNextAction.STOP,
            }
        )

    async def _parse_with_one_transient_retry(
        self, state: MealAgentState
    ) -> tuple[ParseMealResult | None, MealAgentState]:
        """Retry only a classified transient provider failure once.

        The retry is deliberately local to the provider call.  Catalog misses, validation
        failures and unknown provider outcomes are deterministic terminal paths, not retry fuel.
        """

        current = state
        for attempt in range(2):
            if current.budget.model_calls >= 4:
                return None, _limit_state(current)
            current = current.model_copy(
                update={"budget": current.budget.model_copy(update={"model_calls": current.budget.model_calls + 1})}
            )
            try:
                parsed = await self._provider.parse_meal(
                    ParseMealRequest(meal_description=current.messages[0])
                )
            except ProviderCallError as error:
                if error.kind is ProviderFailureKind.TRANSIENT and attempt == 0:
                    continue
                return None, current.model_copy(
                    update={"status": AgentRuntimeStatus.FAILED, "next_action": AgentNextAction.STOP}
                )
            next_cost = current.budget.estimated_cost_usd + parsed.metadata.usage.cost_usd
            if next_cost > Decimal("0.02"):
                return None, _limit_state(current)
            return parsed, current.model_copy(
                update={"budget": current.budget.model_copy(update={"estimated_cost_usd": next_cost})}
            )
        raise AssertionError("provider retry loop must return")

    def _finish_transition(self, state: MealAgentState, started_ms: int) -> MealAgentState:
        """Charge only executing time; waiting between user turns is outside active budget."""

        elapsed = max(0, self._monotonic_ms() - started_ms)
        total = state.budget.active_elapsed_ms + elapsed
        if total > 45_000:
            return _limit_state(state)
        return state.model_copy(
            update={"budget": state.budget.model_copy(update={"active_elapsed_ms": total})}
        )

    def _apply_resume(self, state: MealAgentState, payload: dict[str, object]) -> MealAgentState:
        """Validate all answers before changing state, preventing half-applied interrupts."""

        answers = payload.get("answers")
        if not isinstance(answers, dict) or not answers:
            return state
        questions = {question.item_id: question for question in state.clarification_questions}
        if not set(answers).issubset(questions):
            return state
        changed: dict[str, StateMealItem] = {item.item_id: item for item in state.items}
        for item_id, answer in answers.items():
            question = questions[item_id]
            item = changed.get(item_id)
            if item is None or not isinstance(answer, dict):
                return state
            if answer.get("exclude") is True:
                changed[item_id] = item.model_copy(update={"is_dirty": False, "nutrients": None})
                continue
            if question.field == "grams":
                grams = _decimal_answer(answer.get("grams"))
                if grams is None:
                    return state
                changed[item_id] = item.model_copy(
                    update={"grams": grams, "input_version": _next_version(item.input_version), "is_dirty": True}
                )
                continue
            if question.field == "food":
                candidate_id = answer.get("candidate_id")
                catalog_version = answer.get("catalog_version")
                if not isinstance(candidate_id, str) or not isinstance(catalog_version, str):
                    return state
                candidate = next(
                    (entry for entry in question.candidates if str(entry.food_id) == candidate_id), None
                )
                if candidate is None or catalog_version != candidate.catalog_version:
                    return state
                changed[item_id] = item.model_copy(
                    update={
                        "food_id": candidate.food_id,
                        "catalog_version": candidate.catalog_version,
                        "normalized_name": candidate.label,
                        "input_version": _next_version(item.input_version),
                        "is_dirty": True,
                    }
                )
                continue
            return state
        unresolved = tuple(question for question in state.clarification_questions if question.item_id not in answers)
        excluded = tuple(item_id for item_id, answer in answers.items() if isinstance(answer, dict) and answer.get("exclude") is True)
        return state.model_copy(
            update={
                "items": tuple(changed.values()),
                "clarification_questions": unresolved,
                "missing_fields": tuple(question.item_id + ":" + question.field for question in unresolved),
                "unaccounted_items": tuple(dict.fromkeys((*state.unaccounted_items, *excluded))),
                "dirty_item_ids": tuple(item_id for item_id, item in changed.items() if item.is_dirty),
                "status": AgentRuntimeStatus.ACCEPTED,
                "next_action": AgentNextAction.RESOLVE_CATALOG,
            }
        )

    def _apply_correction(self, state: MealAgentState, payload: dict[str, object]) -> MealAgentState:
        """Apply an already-validated structured correction without re-parsing known items."""

        corrections = payload.get("corrections")
        if not isinstance(corrections, dict) or not corrections:
            return state
        items = {item.item_id: item for item in state.items}
        unaccounted = set(state.unaccounted_items)
        for item_id, correction in corrections.items():
            item = items.get(item_id)
            if item is None or not isinstance(correction, dict):
                return state
            if correction.get("exclude") is True:
                items.pop(item_id)
                unaccounted.add(item_id)
                continue
            grams = correction.get("grams")
            name = correction.get("name")
            if grams is not None:
                parsed_grams = _decimal_answer(grams)
                if parsed_grams is None:
                    return state
                item = item.model_copy(update={"grams": parsed_grams, "is_dirty": True})
            if name is not None:
                if not isinstance(name, str) or not name.strip():
                    return state
                item = item.model_copy(
                    update={"normalized_name": name.strip(), "search_query": name.strip(), "food_id": None, "catalog_version": None, "is_dirty": True}
                )
                unaccounted.discard(item_id)
            items[item_id] = item.model_copy(update={"input_version": _next_version(item.input_version)})
        return state.model_copy(
            update={
                "items": tuple(items.values()),
                "dirty_item_ids": tuple(item_id for item_id, item in items.items() if item.is_dirty),
                "unaccounted_items": tuple(sorted(unaccounted)),
                "report": None,
                "status": AgentRuntimeStatus.ACCEPTED,
                "next_action": AgentNextAction.RESOLVE_CATALOG,
            }
        )

    async def _resolve(self, state: MealAgentState) -> MealAgentState:
        """Run deterministic tools only for new/dirty items and build one combined interrupt."""

        questions: list[ClarificationQuestion] = list(state.clarification_questions)
        updated: list[StateMealItem] = []
        summaries = list(state.tool_summaries)
        unaccounted = list(state.unaccounted_items)
        tool_calls = state.budget.tool_calls
        for item in state.items:
            if item.item_id in unaccounted:
                updated.append(item.model_copy(update={"is_dirty": False, "nutrients": None}))
                continue
            if not item.is_dirty and item.nutrients is not None:
                updated.append(item)
                continue
            if item.grams is None and item.portion_description is None:
                questions.append(_grams_question(item))
                updated.append(item.model_copy(update={"is_dirty": False}))
                continue
            selected_food_id = item.food_id
            catalog_version = item.catalog_version
            if selected_food_id is not None and catalog_version is not None:
                # A checkpoint candidate is a user-facing proposal, never authorization.  The
                # resumed id/version must be found again through the current qualified search
                # before calculation can consume it; a revoked or superseded proposal re-asks.
                if tool_calls >= 12:
                    return _limit_state(state)
                search = await self._tools.search_food_catalog(
                    FoodSearchInput(query=item.search_query or item.normalized_name)
                )
                tool_calls += 1
                summaries.append(_summary(item.item_id, "search", search.action.value, search))
                selected = search.selected_food
                still_offered = (
                    selected is not None
                    and selected.id == selected_food_id
                    and selected.catalog_version == catalog_version
                ) or any(
                    candidate.food_id == selected_food_id and candidate.catalog_version == catalog_version
                    for candidate in search.candidates
                )
                if not still_offered:
                    if search.candidates:
                        questions.append(_food_question(item, search.candidates))
                    elif item.item_id not in unaccounted:
                        unaccounted.append(item.item_id)
                    updated.append(item.model_copy(update={"food_id": None, "catalog_version": None, "is_dirty": False, "nutrients": None}))
                    continue
            else:
                if tool_calls >= 12:
                    return _limit_state(state)
                search = await self._tools.search_food_catalog(FoodSearchInput(query=item.search_query or item.normalized_name))
                tool_calls += 1
                summaries.append(_summary(item.item_id, "search", search.action.value, search))
                if search.selected_food is None:
                    if search.candidates:
                        questions.append(_food_question(item, search.candidates))
                    elif item.item_id not in unaccounted:
                        unaccounted.append(item.item_id)
                    updated.append(item.model_copy(update={"is_dirty": False, "nutrients": None}))
                    continue
                if (
                    item.estimate_confidence is not None
                    and item.estimate_confidence < Decimal("0.7")
                ):
                    questions.append(_exact_food_question(item, search.selected_food))
                    updated.append(item.model_copy(update={"is_dirty": False, "nutrients": None}))
                    continue
                selected_food_id = search.selected_food.id
                catalog_version = search.selected_food.catalog_version
            if tool_calls >= 12:
                return _limit_state(state)
            calculation = self._tools.calculate_nutrition(
                NutritionCalculationInput(
                    food_id=selected_food_id,
                    catalog_version=catalog_version,
                    grams=item.grams,
                    portion_description=item.portion_description,
                )
            )
            tool_calls += 1
            summaries.append(_summary(item.item_id, "calculate", calculation.action.value, calculation))
            if tool_calls >= 12:
                return _limit_state(state)
            validation = self._tools.validate_nutrition_result(NutritionValidationInput(calculation=calculation))
            tool_calls += 1
            summaries.append(_summary(item.item_id, "validate", validation.action.value, validation))
            if calculation.nutrients is None or calculation.food is None or validation.action.value not in {"PASS", "WARN"}:
                questions.append(_grams_question(item))
                updated.append(item.model_copy(update={"is_dirty": False, "nutrients": None}))
                continue
            food = calculation.food
            nutrients = calculation.nutrients
            updated.append(
                item.model_copy(
                    update={
                        "normalized_name": food.canonical_name,
                        "food_id": food.id,
                        "catalog_version": food.catalog_version,
                        "grams": calculation.grams,
                        "is_dirty": False,
                        "nutrients": StateNutritionResult(
                            energy_kcal=nutrients.energy_kcal,
                            protein_g=nutrients.protein_g,
                            fat_g=nutrients.fat_g,
                            carbohydrate_g=nutrients.carbohydrate_g,
                            source_name=food.source_name,
                            source_url=food.source_url,
                            calculation_rule_version=calculation.calculation_rule_version,
                        ),
                    }
                )
            )
        result = state.model_copy(
            update={
                "items": tuple(updated),
                "tool_summaries": tuple(summaries),
                "clarification_questions": tuple(questions),
                "missing_fields": tuple(question.item_id + ":" + question.field for question in questions),
                "unaccounted_items": tuple(dict.fromkeys(unaccounted)),
                "dirty_item_ids": (),
                "messages": (),
                "budget": state.budget.model_copy(update={"tool_calls": tool_calls}),
            }
        )
        catalog_version = next(
            (item.catalog_version for item in result.items if item.catalog_version is not None),
            None,
        )
        retrieve_context = getattr(self._tools, "retrieve_personal_context", None)
        if catalog_version is not None and callable(retrieve_context):
            # Re-read after catalog resolution so controlled knowledge is bound to exactly the
            # version that deterministic calculation used, never to a floating latest catalog.
            query = next((item.normalized_name for item in result.items), "")
            hints = retrieve_context(user_id=result.user_id, query=query, catalog_version=catalog_version)
            result = result.model_copy(
                update={
                    "context_hints": tuple(
                        StateContextHint(source=hint.source, summary=hint.summary)
                        for hint in hints[:9]
                    )
                }
            )
        if questions:
            return result.model_copy(
                update={
                    "status": AgentRuntimeStatus.WAITING_INPUT,
                    "next_action": AgentNextAction.ASK_USER,
                    "report": _build_report(result, waiting=True),
                }
            )
        return result.model_copy(
            update={
                "status": AgentRuntimeStatus.COMPLETED,
                "next_action": AgentNextAction.REPORT,
                "is_partial": bool(result.unaccounted_items),
                "report": _build_report(result, waiting=False),
            }
        )


def _begin_transition(state: MealAgentState) -> MealAgentState:
    """Reject the *next* graph transition before it can trigger model or tools."""

    if state.budget.graph_steps >= 12 or state.budget.active_elapsed_ms >= 45_000 or state.budget.estimated_cost_usd >= Decimal("0.02"):
        return _limit_state(state)
    return state.model_copy(
        update={"budget": state.budget.model_copy(update={"graph_steps": state.budget.graph_steps + 1})}
    )


def _limit_state(state: MealAgentState) -> MealAgentState:
    return state.model_copy(
        update={"status": AgentRuntimeStatus.LIMIT_REACHED, "next_action": AgentNextAction.STOP}
    )


def _vision_result_state(state: MealAgentState, observed: VisionMealResult) -> MealAgentState:
    """Project a strict provider DTO into the distinct graph-state contract."""

    items = tuple(
        StateMealItem(
            item_id=item.item_id,
            normalized_name=item.food_name,
            grams=item.estimated_grams,
            portion_description=item.portion_clue,
            input_version="vision.v1",
            is_dirty=True,
            search_query=item.food_name,
            is_estimated=item.estimated_grams is not None,
            estimate_confidence=item.confidence,
        )
        for item in observed.items
    )
    metadata = observed.metadata
    return state.model_copy(
        update={
            "items": items,
            "messages": (),
            "vision_metadata": StateVisionMetadata(
                model_alias=metadata.model_alias,
                provider_request_id=metadata.provider_request_id,
                image_tokens=metadata.usage.image_tokens,
                prompt_tokens=metadata.usage.prompt_tokens,
                completion_tokens=metadata.usage.completion_tokens,
                cost_cny=metadata.usage.cost_cny,
                latency_ms=metadata.latency_ms,
                prompt_version=metadata.prompt_version,
                schema_version=metadata.schema_version,
            ),
            "vision_invocation_status": "completed",
            "next_action": AgentNextAction.RESOLVE_CATALOG,
            "status": AgentRuntimeStatus.ACCEPTED,
        }
    )


def _monotonic_ms() -> int:
    from time import monotonic

    return int(monotonic() * 1000)


def _decimal_answer(value: object) -> Decimal | None:
    from app.agent.weight import InvalidWeightInput, parse_weight_grams

    try:
        return parse_weight_grams(value)
    except InvalidWeightInput:
        return None


def _recover_single_explicit_grams(
    *, message: str, items: tuple[StateMealItem, ...]
) -> tuple[str, Decimal] | None:
    """Recover one literal grams value the provider omitted, without inferring food facts.

    A model observation is allowed to identify food, but it must not make an explicit user
    quantity disappear.  The narrow shape below avoids assigning one quantity across a mixed
    meal: exactly one parsed item, exactly one ``g``/``克`` literal, and no model-supplied grams.
    """

    if len(items) != 1 or items[0].grams is not None:
        return None
    matches = _EXPLICIT_GRAMS.findall(message)
    if len(matches) != 1:
        return None
    grams = _decimal_answer(matches[0])
    return (items[0].item_id, grams) if grams is not None else None


def _recover_single_portion_description(
    *, message: str, items: tuple[StateMealItem, ...]
) -> tuple[str, str] | None:
    """Preserve a single item's residual quantity phrase; the catalog decides usability.

    This deliberately has no list of portions.  The parser only separates a recognized food
    name from the remaining user text; ``calculate_nutrition`` accepts that residual only when
    the matched food owns one exact, audited controlled portion with the same description.
    """

    if len(items) != 1 or items[0].grams is not None or items[0].portion_description:
        return None
    normalized_message = "".join(message.casefold().split())
    normalized_food = "".join(items[0].normalized_name.casefold().split())
    if not normalized_food or normalized_message.count(normalized_food) != 1:
        return None
    portion_description = normalized_message.replace(normalized_food, "", 1).strip("，,。.")
    if not portion_description:
        return None
    return items[0].item_id, portion_description


def _next_version(value: str) -> str:
    prefix, separator, suffix = value.rpartition(".v")
    if separator and suffix.isdecimal():
        return f"{prefix}.v{int(suffix) + 1}"
    return f"{value}.v2"


def _summary(item_id: str, tool_name: str, action: str, result: object) -> StateToolSummary:
    return StateToolSummary(
        tool_name=f"{tool_name}:{item_id}",
        tool_version="nutrition-tools-v1",
        action=action,
        result_digest=_digest(result),
    )


def _grams_question(item: StateMealItem) -> ClarificationQuestion:
    return ClarificationQuestion(
        item_id=item.item_id,
        field="grams",
        message=f"请补充“{item.normalized_name}”的可审计克数。",
    )


def _food_question(
    item: StateMealItem, candidates: tuple[FoodSearchCandidate, ...]
) -> ClarificationQuestion:
    safe_candidates = tuple(
        StateCandidate(
            item_id=item.item_id,
            food_id=candidate.food_id,
            catalog_version=candidate.catalog_version,
            label=(
                f"{candidate.canonical_name}（{candidate.prepared_state}）"
                if candidate.prepared_state is not None
                else candidate.canonical_name
            ),
            canonical_label=candidate.canonical_name,
            relation_label=candidate.relation.value,
            prepared_state=candidate.prepared_state,
            portion_hints=candidate.portion_hints,
            source_name=candidate.source_name,
        )
        for candidate in candidates[:3]
    )
    return ClarificationQuestion(
        item_id=item.item_id,
        field="food",
        message=f"请从“{item.normalized_name}”的候选食物中选择一项。",
        candidates=safe_candidates,
    )


def _exact_food_question(item: StateMealItem, food: QualifiedFood) -> ClarificationQuestion:
    """Low-confidence exact confirmation does not invent a non-exact relation."""

    return ClarificationQuestion(
        item_id=item.item_id,
        field="food",
        message=f"请确认“{item.normalized_name}”是否为该受控目录条目。",
        candidates=(
            StateCandidate(
                item_id=item.item_id,
                food_id=food.id,
                catalog_version=food.catalog_version,
                label=f"{food.canonical_name}（{food.prepared_state}）",
                canonical_label=food.canonical_name,
                prepared_state=food.prepared_state,
                portion_hints=tuple(
                    portion.description for portion in food.portions if portion.audited
                )[:3],
                source_name=food.source_name,
            ),
        ),
    )


def _build_report(state: MealAgentState, *, waiting: bool) -> dict[str, object]:
    values = [(item, item.nutrients) for item in state.items if item.nutrients is not None]
    totals = {
        field: sum((getattr(nutrients, field) for _item, nutrients in values), Decimal("0"))
        for field in ("energy_kcal", "protein_g", "fat_g", "carbohydrate_g")
    }
    return {
        "items": [
            {
                "item_id": item.item_id,
                "name": item.normalized_name,
                "food_id": str(item.food_id),
                "catalog_version": item.catalog_version,
                "grams": str(item.grams),
                "is_estimated": item.is_estimated,
                "estimate_confidence": str(item.estimate_confidence) if item.estimate_confidence is not None else None,
                "energy_kcal": str(nutrients.energy_kcal.quantize(Decimal("0.1"))),
                "protein_g": str(nutrients.protein_g.quantize(Decimal("0.1"))),
                "fat_g": str(nutrients.fat_g.quantize(Decimal("0.1"))),
                "carbohydrate_g": str(nutrients.carbohydrate_g.quantize(Decimal("0.1"))),
                "source_name": nutrients.source_name,
                "source_url": nutrients.source_url,
                "calculation_rule_version": nutrients.calculation_rule_version,
            }
            for item, nutrients in values
        ],
        "understood_items": [
            {
                "item_id": item.item_id,
                "name": item.normalized_name,
                "grams": str(item.grams) if item.grams is not None else None,
                "is_estimated": item.is_estimated,
                "estimate_confidence": str(item.estimate_confidence) if item.estimate_confidence is not None else None,
            }
            for item in state.items
        ],
        "questions": [question.model_dump(mode="json") for question in state.clarification_questions],
        "unaccounted_items": list(state.unaccounted_items),
        "is_partial": bool(state.unaccounted_items),
        "waiting_input": waiting,
        "totals": {field: str(value.quantize(Decimal("0.1"))) for field, value in totals.items()},
        "disclaimer": "普通饮食参考，不替代医疗建议。",
        "context_references": [hint.summary for hint in state.context_hints],
    }


def route_main_graph(intent: AgentIntent) -> GraphRoute:
    """Keep the main graph's two supported subgraph routes explicit and closed."""

    if intent is AgentIntent.MEAL_ANALYSIS:
        return GraphRoute.MEAL_ANALYSIS
    return GraphRoute.DIET_PLANNING


def diet_planning_not_available(state: MealAgentState) -> MealAgentState:
    """Phase 2 must not imply that the Phase 5 planner exists or produced advice."""

    return state.model_copy(
        update={
            "next_action": AgentNextAction.STOP,
            "status": AgentRuntimeStatus.FAILED,
            "report": {
                "code": "CAPABILITY_NOT_AVAILABLE",
                "message": "饮食规划能力尚未交付。",
            },
        }
    )


class DietPlanningGraph:
    """Bounded planning subgraph that can only invoke the typed planning tool port."""

    def __init__(self, *, tools: PlanningToolAdapter) -> None:
        self._tools = tools

    async def ainvoke(
        self, state: DietPlanningState, *, resume: dict[str, object] | None = None
    ) -> DietPlanningState:
        if state.status in {
            AgentRuntimeStatus.LIMIT_REACHED,
            AgentRuntimeStatus.FAILED,
        }:
            return state
        if resume is not None:
            return await self._apply_adjustment(state, resume)
        if state.status is AgentRuntimeStatus.COMPLETED:
            return state
        if not state.preferences.confirmed:
            return state.model_copy(
                update={
                    "status": AgentRuntimeStatus.WAITING_INPUT,
                    "next_action": DietPlanningAction.NEEDS_INPUT,
                    "report": {
                        "stage": "needs_input",
                        "message": "请确认本次资料与饮食偏好后继续。",
                    },
                }
            )

        current = state
        target_result = self._tools.calculate_daily_target(
            profile=current.profile, preferences=current.preferences
        )
        current = self._record_tool(current, "calculate_targets", target_result.action.value, target_result)
        if target_result.action is not PlanValidationAction.PASS or target_result.target is None:
            return self._safe_terminal(current, target_result.action, target_result.safe_message)
        current = current.model_copy(
            update={"target": target_result.target, "next_action": DietPlanningAction.COMPOSE_PLAN}
        )
        # A health-scope refusal must not persist the transient command as a profile.  Saving is
        # intentionally deferred until the deterministic health guard has accepted the request.
        if current.save_profile and not current.profile_save_completed:
            current = self._call_profile_upsert(current)

        while current.replan_count < 3:
            composition = self._tools.compose_daily_plan(
                user_id=current.user_id,
                target=target_result.target,
                preferences=current.preferences,
                replan_count=current.replan_count,
            )
            current = self._record_tool(
                current, "compose_plan", composition.action.value, composition
            )
            if composition.action is not PlanValidationAction.PASS:
                current = current.model_copy(update={"replan_count": current.replan_count + 1})
                continue

            validation = self._tools.validate_daily_plan(
                target=target_result.target,
                meals=composition.meals,
                replan_count=current.replan_count,
            )
            current = self._record_tool(
                current, "validate_plan", validation.action.value, validation
            )
            if validation.action is PlanValidationAction.PASS:
                report = _planning_report(target=target_result.target, meals=composition.meals)
                return current.model_copy(
                    update={
                        "meals": composition.meals,
                        "next_action": DietPlanningAction.COMPLETE,
                        "status": AgentRuntimeStatus.COMPLETED,
                        "report": report,
                    }
                )
            if validation.action is PlanValidationAction.RELAX:
                # Relaxation is a bounded, deterministic fallback.  It must remain
                # visible in the public report instead of being mistaken for a hard
                # target pass or falling through into a meaningless retry loop.
                report = _planning_report(target=target_result.target, meals=composition.meals)
                report.update(
                    _relaxation_projection(
                        target=target_result.target,
                        meals=composition.meals,
                        reason=validation.safe_message,
                    )
                )
                return current.model_copy(
                    update={
                        "meals": composition.meals,
                        "next_action": DietPlanningAction.COMPLETE,
                        "status": AgentRuntimeStatus.COMPLETED,
                        "report": report,
                    }
                )
            if validation.action is PlanValidationAction.BLOCK_HEALTH_SCOPE:
                return self._safe_terminal(current, validation.action, validation.safe_message)
            current = current.model_copy(update={"replan_count": current.replan_count + 1})

        return current.model_copy(
            update={
                "status": AgentRuntimeStatus.LIMIT_REACHED,
                "next_action": DietPlanningAction.NEEDS_INPUT,
                "report": {
                    "stage": "needs_input",
                    "message": "无法在三次调整内满足所有约束；请修改资料或新建计划。",
                },
            }
        )

    async def _apply_adjustment(self, state: DietPlanningState, resume: dict[str, object]) -> DietPlanningState:
        if state.replan_count >= 3:
            return self._adjustment_limit(state)
        feedback = resume.get("feedback")
        selected_slot = resume.get("slot")
        current = state
        intent = current.pending_adjustment_intent
        slot = current.pending_adjustment_slot
        if isinstance(feedback, str) and 1 <= len(feedback) <= 500:
            intent = "lighter" if "清淡" in feedback else "replace"
            slot = _slot_from_feedback(feedback)
            food_query = _food_query_from_feedback(feedback)
            current = self._capture_adjustment_preferences(current, feedback)
            current = current.model_copy(
                update={
                    "pending_adjustment_intent": intent,
                    "pending_adjustment_slot": slot,
                    "pending_food_query": food_query,
                    "pending_food_candidates": (),
                }
            )
            if slot is None:
                return current.model_copy(
                    update={
                        "status": AgentRuntimeStatus.WAITING_INPUT,
                        "next_action": DietPlanningAction.NEEDS_INPUT,
                        "report": {
                            "stage": "needs_input",
                            "message": "请选择要调整的餐次。",
                            "input_choices": [meal.slot.value for meal in current.meals],
                        },
                    }
                )
        elif current.pending_food_candidates:
            # Candidate identity is validated below against both the offered checkpoint
            # projection and a fresh catalog read before it can affect composition.
            pass
        elif (
            isinstance(selected_slot, str)
            and intent is not None
            and selected_slot in {meal.slot.value for meal in current.meals}
        ):
            slot = MealSlot(selected_slot)
            current = current.model_copy(update={"pending_adjustment_slot": slot})
        else:
            return state
        target = current.target
        if target is None or len(current.meals) not in (3, 4) or slot is None or intent is None:
            return state

        selected_food_id = None
        selected_catalog_version = None
        if current.pending_food_candidates:
            candidate_id = resume.get("candidate_id")
            catalog_version = resume.get("catalog_version")
            candidate = next(
                (entry for entry in current.pending_food_candidates if str(entry.food_id) == candidate_id), None
            )
            if candidate is None or catalog_version != candidate.catalog_version or current.pending_food_query is None:
                return state
            search = await self._tools.search_food_catalog(FoodSearchInput(query=current.pending_food_query))
            candidate_is_current = any(
                food.food_id == candidate.food_id and food.catalog_version == candidate.catalog_version
                for food in search.candidates
            ) or (
                search.selected_food is not None
                and search.selected_food.id == candidate.food_id
                and search.selected_food.catalog_version == candidate.catalog_version
            )
            if not candidate_is_current:
                return current.model_copy(
                    update={
                        "pending_food_candidates": (),
                        "pending_food_query": None,
                        "status": AgentRuntimeStatus.WAITING_INPUT,
                        "next_action": DietPlanningAction.NEEDS_INPUT,
                        "report": {"stage": "needs_input", "message": "所选菜品已不再可用，请重新输入菜名。"},
                    }
                )
            selected_food_id = candidate.food_id
            selected_catalog_version = candidate.catalog_version
            current = current.model_copy(update={"pending_food_candidates": (), "pending_food_query": None})
        elif current.pending_food_query:
            search = await self._tools.search_food_catalog(FoodSearchInput(query=current.pending_food_query))
            if search.selected_food is not None:
                selected_food_id = search.selected_food.id
                selected_catalog_version = search.selected_food.catalog_version
                current = current.model_copy(update={"pending_food_query": None})
            elif search.candidates:
                candidates = tuple(
                    StateCandidate(
                        item_id="planning-substitution",
                        food_id=food.food_id,
                        catalog_version=food.catalog_version,
                        label=f"{food.canonical_name}（{food.prepared_state}）" if food.prepared_state is not None else food.canonical_name,
                        canonical_label=food.canonical_name,
                        relation_label=food.relation.value,
                        prepared_state=food.prepared_state,
                        portion_hints=food.portion_hints,
                        source_name=food.source_name,
                    )
                    for food in search.candidates
                )
                return current.model_copy(
                    update={
                        "pending_food_candidates": candidates,
                        "status": AgentRuntimeStatus.WAITING_INPUT,
                        "next_action": DietPlanningAction.NEEDS_INPUT,
                        "report": {
                            "stage": "food_clarification",
                            "message": "请选择要用于替换的受控菜品。",
                            "candidates": [candidate.model_dump(mode="json") for candidate in candidates],
                        },
                    }
                )
            else:
                return current.model_copy(
                    update={
                        "status": AgentRuntimeStatus.WAITING_INPUT,
                        "next_action": DietPlanningAction.NEEDS_INPUT,
                        "report": {"stage": "needs_input", "message": "目录中没有可用于替换的菜品，请更换名称。"},
                    }
                )
        composition = self._tools.replace_planning_slot(
            user_id=current.user_id,
            target=target,
            preferences=current.preferences,
            existing_meals=current.meals,
            affected_slot=slot,
            feedback_intent=intent,
            selected_food_id=selected_food_id,
            selected_catalog_version=selected_catalog_version,
            replan_count=current.replan_count,
        )
        current = self._record_tool(current, "replace_planning_slot", composition.action.value, composition)
        if composition.action is not PlanValidationAction.PASS:
            return self._safe_terminal(current, composition.action, composition.safe_message)
        validation = self._tools.validate_daily_plan(
            target=target, meals=composition.meals, replan_count=current.replan_count
        )
        current = self._record_tool(current, "validate_plan", validation.action.value, validation)
        if validation.action is PlanValidationAction.BLOCK_HEALTH_SCOPE:
            return self._safe_terminal(current, validation.action, validation.safe_message)
        if validation.action is PlanValidationAction.NEEDS_INPUT:
            return self._safe_terminal(current, validation.action, validation.safe_message)
        if validation.action is PlanValidationAction.REPLAN:
            return self._safe_terminal(current, validation.action, validation.safe_message)
        next_count = current.replan_count + 1
        report = _planning_report(target=target, meals=composition.meals)
        report["adjustment"] = {
            "changed_slots": [slot.value],
            "matched_constraint": "清淡" if intent == "lighter" else "已确认调整",
            "range_status": _range_statuses(target=target, meals=composition.meals),
            **(_relaxation_projection(target=target, meals=composition.meals, reason=validation.safe_message)
               if validation.action is PlanValidationAction.RELAX else {}),
        }
        return current.model_copy(
            update={
                "meals": composition.meals,
                "replan_count": next_count,
                "pending_adjustment_intent": None,
                "pending_adjustment_slot": None,
                "pending_food_query": None,
                "pending_food_candidates": (),
                "next_action": DietPlanningAction.COMPLETE,
                "status": AgentRuntimeStatus.COMPLETED,
                "report": report,
            }
        )

    def _capture_adjustment_preferences(self, state: DietPlanningState, feedback: str) -> DietPlanningState:
        marker = hashlib.sha256(feedback.encode("utf-8")).hexdigest()
        if marker in state.preference_capture_markers:
            return state
        captured = self._tools.capture_explicit_preferences(user_id=state.user_id, run_id=state.run_id, statement=feedback)
        exclusions = list(state.preferences.exclusions)
        tastes = list(state.preferences.taste_preferences)
        for summary in captured:
            if summary.category == "avoidance" and summary.canonical_text.startswith("不吃"):
                item = summary.canonical_text.removeprefix("不吃")
                if item and item not in exclusions:
                    exclusions.append(item)
            elif summary.category == "stable_preference" and summary.canonical_text not in tastes:
                tastes.append(summary.canonical_text)
        return state.model_copy(
            update={
                "preferences": PreferenceReview(confirmed=True, exclusions=tuple(exclusions), taste_preferences=tuple(tastes)),
                "preference_capture_markers": (*state.preference_capture_markers, marker),
            }
        )

    @staticmethod
    def _adjustment_limit(state: DietPlanningState) -> DietPlanningState:
        return state.model_copy(update={"status": AgentRuntimeStatus.LIMIT_REACHED, "next_action": DietPlanningAction.NEEDS_INPUT, "pending_adjustment_intent": None, "pending_adjustment_slot": None, "pending_food_query": None, "pending_food_candidates": (), "report": {"stage": "needs_input", "code": "LIMIT_REACHED", "message": "本次计划已达到三次调整上限；请新建计划或修改资料与目标。"}})

    def _call_profile_upsert(self, state: DietPlanningState) -> DietPlanningState:
        if state.budget.tool_calls >= 12:
            return self._budget_limit(state)
        self._tools.upsert_planning_profile(
            user_id=state.user_id, profile=state.profile, command_key=state.command_key
        )
        updated = self._record_tool(state, "save_profile", "saved", (state.user_id, state.command_key))
        return updated.model_copy(update={"profile_save_completed": True})

    def _record_tool(
        self, state: DietPlanningState, name: str, action: str, result: object
    ) -> DietPlanningState:
        if state.budget.tool_calls >= 12:
            return self._budget_limit(state)
        return state.model_copy(
            update={
                "tool_summaries": (
                    *state.tool_summaries,
                    StateToolSummary(
                        tool_name=name,
                        tool_version="planning-tools.v1",
                        action=action,
                        result_digest=_digest(result),
                    ),
                ),
                "budget": state.budget.model_copy(
                    update={
                        "graph_steps": min(state.budget.graph_steps + 1, 12),
                        "tool_calls": state.budget.tool_calls + 1,
                    }
                ),
            }
        )

    @staticmethod
    def _budget_limit(state: DietPlanningState) -> DietPlanningState:
        return state.model_copy(
            update={
                "status": AgentRuntimeStatus.LIMIT_REACHED,
                "next_action": DietPlanningAction.NEEDS_INPUT,
                "report": {"stage": "needs_input", "message": "规划已达到本次运行上限。"},
            }
        )

    @staticmethod
    def _safe_terminal(
        state: DietPlanningState, action: PlanValidationAction, message: str
    ) -> DietPlanningState:
        if action is PlanValidationAction.NEEDS_INPUT:
            status = AgentRuntimeStatus.WAITING_INPUT
        elif action is PlanValidationAction.BLOCK_HEALTH_SCOPE:
            status = AgentRuntimeStatus.FAILED
        else:
            status = AgentRuntimeStatus.LIMIT_REACHED
        return state.model_copy(
            update={
                "status": status,
                "next_action": DietPlanningAction.NEEDS_INPUT,
                "report": {"stage": "needs_input", "message": message},
            }
        )


class RoutedAgentGraph:
    """Closed main-graph dispatcher; every supported state has exactly one subgraph."""

    def __init__(self, *, meal_graph: MealAnalysisGraph, diet_planning_graph: DietPlanningGraph) -> None:
        self._meal_graph = meal_graph
        self._diet_planning_graph = diet_planning_graph

    async def ainvoke(
        self, state: MealAgentState | DietPlanningState, *, resume: dict[str, object] | None = None
    ) -> MealAgentState | DietPlanningState:
        if isinstance(state, MealAgentState):
            return await self._meal_graph.ainvoke(state, resume=resume)
        if isinstance(state, DietPlanningState):
            return await self._diet_planning_graph.ainvoke(state, resume=resume)
        raise TypeError("unsupported agent graph state")


def _planning_report(*, target: object, meals: tuple[object, ...]) -> dict[str, object]:
    """Project the deterministic plan into the only report shape public clients can receive."""

    from app.planning.schemas import DailyTarget, PlannedMeal

    assert isinstance(target, DailyTarget)
    planning_meals = tuple(meal for meal in meals if isinstance(meal, PlannedMeal))
    return {
        "stage": "complete",
        "target": {
            field: {"lower": str(getattr(target, field).lower), "upper": str(getattr(target, field).upper)}
            for field in ("energy_kcal", "carbohydrate_g", "protein_g", "fat_g")
        },
        "meals": [
            {
                "slot": meal.slot.value,
                "display_name": meal.display_name,
                "portion_description": meal.portion_description,
                "portion_grams": str(meal.portion_grams),
                "method_tags": list(meal.method_tags),
                "flavour_tags": list(meal.flavour_tags),
                "matched_preference_summaries": list(meal.matched_preference_summaries),
                "matched_exclusion_summaries": list(meal.matched_exclusion_summaries),
                "nutrients": {
                    field: str(getattr(meal.nutrients, field))
                    for field in ("energy_kcal", "protein_g", "fat_g", "carbohydrate_g")
                },
            }
            for meal in planning_meals
        ],
        "disclaimer": "普通饮食参考，不替代医疗建议。",
    }


def _slot_from_feedback(feedback: str) -> MealSlot | None:
    matches = [
        slot
        for slot, labels in (
            (MealSlot.BREAKFAST, ("早餐", "breakfast")),
            (MealSlot.LUNCH, ("午餐", "lunch")),
            (MealSlot.DINNER, ("晚餐", "dinner")),
            (MealSlot.SNACK, ("加餐", "snack")),
        )
        if any(label in feedback.casefold() for label in labels)
    ]
    return matches[0] if len(matches) == 1 else None


def _food_query_from_feedback(feedback: str) -> str | None:
    """Extract only an explicitly requested replacement name from adjustment text."""

    match = re.search(
        r"(?:替换成|替换为|换成|换为|改成|改为|想吃)\s*([^,，。；;！？!?]+)",
        feedback,
    )
    if match is None:
        return None
    query = re.sub(r"(?:吧|可以吗|行吗)$", "", match.group(1).strip()).strip()
    return query if 1 <= len(query) <= 200 else None


def _range_statuses(*, target: DailyTarget, meals: tuple[PlannedMeal, ...]) -> dict[str, str]:
    totals = {
        field: sum((getattr(meal.nutrients, field) for meal in meals), Decimal("0"))
        for field in ("energy_kcal", "carbohydrate_g", "protein_g", "fat_g")
    }
    return {
        field: "low" if value < getattr(target, field).lower else "high" if value > getattr(target, field).upper else "in_range"
        for field, value in totals.items()
    }


def _relaxation_projection(*, target: DailyTarget, meals: tuple[PlannedMeal, ...], reason: str) -> dict[str, object]:
    totals = {
        field: sum((getattr(meal.nutrients, field) for meal in meals), Decimal("0"))
        for field in ("energy_kcal", "carbohydrate_g", "protein_g", "fat_g")
    }
    for field, value in totals.items():
        bounds = getattr(target, field)
        if value < bounds.lower or value > bounds.upper:
            deviation = value - (bounds.lower if value < bounds.lower else bounds.upper)
            return {
                "relaxation": {
                    "metric": field,
                    "original_range": {"lower": str(bounds.lower), "upper": str(bounds.upper)},
                    "plan_value": str(value),
                    "deviation": str(deviation),
                    "reason": reason,
                }
            }
    # A service may permit a range relaxation even when this minimal projection is in range.
    bounds = target.energy_kcal
    return {
        "relaxation": {
            "metric": "energy_kcal",
            "original_range": {"lower": str(bounds.lower), "upper": str(bounds.upper)},
            "plan_value": str(totals["energy_kcal"]),
            "deviation": "0",
            "reason": reason,
        }
    }
