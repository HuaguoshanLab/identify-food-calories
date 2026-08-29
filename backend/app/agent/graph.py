"""Pure main-graph routing and lifespan contracts.

This module intentionally contains no SQLAlchemy, ORM or repository import.  A
runtime built in later plans injects a `NutritionToolAdapter` and a persisted
checkpointer after AgentService has already proved thread ownership.
"""

from __future__ import annotations

import hashlib
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
    StateCandidate,
)
from app.agent.tools import NutritionToolAdapter
from app.nutrition.schemas import (
    FoodSearchInput,
    NutritionCalculationInput,
    NutritionValidationInput,
    QualifiedFood,
)
from app.providers.reasoning.dto import ParseMealRequest, ProviderCallError
from app.providers.reasoning.ports import ReasoningModelProvider


GRAPH_VERSION = "meal-agent-graph.v1"


class AgentIntent(StrEnum):
    MEAL_ANALYSIS = "MEAL_ANALYSIS"
    DIET_PLANNING = "DIET_PLANNING"


class GraphRoute(StrEnum):
    MEAL_ANALYSIS = "MEAL_ANALYSIS"
    DIET_PLANNING = "DIET_PLANNING"


class AgentGraph(Protocol):
    """Compiled graph facade used by HTTP/supervisor lifecycles in later plans."""

    async def ainvoke(
        self, state: MealAgentState, *, resume: dict[str, object] | None = None
    ) -> MealAgentState: ...


@dataclass(frozen=True, slots=True)
class AgentRuntime:
    """Long-lived runtime dependencies created once by FastAPI lifespan."""

    graph: AgentGraph
    tools: NutritionToolAdapter
    checkpointer: object
    supervisor: object
    session_factory: Callable[[], object]


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
        self, *, provider: ReasoningModelProvider, tools: NutritionToolAdapter
    ) -> None:
        self._provider = provider
        self._tools = tools

    async def ainvoke(
        self, state: MealAgentState, *, resume: dict[str, object] | None = None
    ) -> MealAgentState:
        """Advance a pure state machine; the service owns persistence and idempotency.

        A waiting state never calls the provider again.  The previous parse/search work is
        already in the checkpoint, so an invalid resume is a no-op and a valid answer only marks
        the affected item dirty before deterministic tools are called again.
        """

        if state.next_action is AgentNextAction.ASK_USER:
            if resume is None:
                return state
            resumed = self._apply_resume(state, resume)
            return self._resolve(resumed) if resumed is not state else state
        if state.next_action is AgentNextAction.REPORT:
            if resume is None:
                return state
            corrected = self._apply_correction(state, resume)
            return self._resolve(corrected) if corrected is not state else state
        if state.next_action is not AgentNextAction.PARSE or len(state.messages) != 1:
            return state.model_copy(
                update={"status": AgentRuntimeStatus.FAILED, "next_action": AgentNextAction.STOP}
            )
        try:
            parsed = await self._provider.parse_meal(
                ParseMealRequest(meal_description=state.messages[0])
            )
        except ProviderCallError:
            return state.model_copy(
                update={"status": AgentRuntimeStatus.FAILED, "next_action": AgentNextAction.STOP}
            )
        items = tuple(
            StateMealItem(
                item_id=item.item_id,
                normalized_name=item.food_name,
                grams=item.grams,
                input_version="v1",
                is_dirty=True,
                search_query=item.catalog_query or item.food_name,
            )
            for item in parsed.value.items
        )
        missing = tuple(
            f"{field.item_id}:{field.field}" for field in parsed.value.missing_fields
        )
        return self._resolve(
            state.model_copy(update={"items": items, "messages": (), "missing_fields": missing})
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
                if not isinstance(candidate_id, str):
                    return state
                candidate = next(
                    (entry for entry in question.candidates if str(entry.food_id) == candidate_id), None
                )
                if candidate is None:
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

    def _resolve(self, state: MealAgentState) -> MealAgentState:
        """Run deterministic tools only for new/dirty items and build one combined interrupt."""

        questions: list[ClarificationQuestion] = list(state.clarification_questions)
        updated: list[StateMealItem] = []
        summaries = list(state.tool_summaries)
        unaccounted = list(state.unaccounted_items)
        for item in state.items:
            if item.item_id in unaccounted:
                updated.append(item.model_copy(update={"is_dirty": False, "nutrients": None}))
                continue
            if not item.is_dirty and item.nutrients is not None:
                updated.append(item)
                continue
            if item.grams is None:
                questions.append(_grams_question(item))
                updated.append(item.model_copy(update={"is_dirty": False}))
                continue
            selected_food_id = item.food_id
            catalog_version = item.catalog_version
            if selected_food_id is None or catalog_version is None:
                search = self._tools.search_food_catalog(FoodSearchInput(query=item.search_query or item.normalized_name))
                summaries.append(_summary(item.item_id, "search", search.action.value, search))
                if search.selected_food is None:
                    if search.candidates:
                        questions.append(_food_question(item, search.candidates))
                    elif item.item_id not in unaccounted:
                        unaccounted.append(item.item_id)
                    updated.append(item.model_copy(update={"is_dirty": False, "nutrients": None}))
                    continue
                selected_food_id = search.selected_food.id
                catalog_version = search.selected_food.catalog_version
            calculation = self._tools.calculate_nutrition(
                NutritionCalculationInput(food_id=selected_food_id, catalog_version=catalog_version, grams=item.grams)
            )
            summaries.append(_summary(item.item_id, "calculate", calculation.action.value, calculation))
            validation = self._tools.validate_nutrition_result(NutritionValidationInput(calculation=calculation))
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


def _decimal_answer(value: object) -> Decimal | None:
    try:
        grams = Decimal(str(value))
    except Exception:
        return None
    return grams if Decimal("0") < grams <= Decimal("2000") else None


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


def _food_question(item: StateMealItem, candidates: tuple[QualifiedFood, ...]) -> ClarificationQuestion:
    safe_candidates = tuple(
        StateCandidate(
            item_id=item.item_id,
            food_id=candidate.id,
            catalog_version=candidate.catalog_version,
            label=f"{candidate.canonical_name}（{candidate.prepared_state}）",
        )
        for candidate in candidates[:3]
    )
    return ClarificationQuestion(
        item_id=item.item_id,
        field="food",
        message=f"请从“{item.normalized_name}”的候选食物中选择一项。",
        candidates=safe_candidates,
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
                "grams": str(item.grams),
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
            {"item_id": item.item_id, "name": item.normalized_name, "grams": str(item.grams) if item.grams is not None else None}
            for item in state.items
        ],
        "questions": [question.model_dump(mode="json") for question in state.clarification_questions],
        "unaccounted_items": list(state.unaccounted_items),
        "is_partial": bool(state.unaccounted_items),
        "waiting_input": waiting,
        "totals": {field: str(value.quantize(Decimal("0.1"))) for field, value in totals.items()},
        "disclaimer": "普通饮食参考，不替代医疗建议。",
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
