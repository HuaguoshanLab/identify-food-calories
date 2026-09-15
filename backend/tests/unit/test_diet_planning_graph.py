"""RED contracts for the bounded, tool-only diet-planning subgraph."""

from __future__ import annotations

import asyncio
import json
import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.agent.graph import DietPlanningGraph
from app.agent.service import AgentService
from app.agent.state import AgentGraphKind, DietPlanningAction, DietPlanningState, MealAgentState
from app.agent.tools import PlanningToolAdapter
from app.nutrition.schemas import FoodRelation, FoodSearchCandidate, FoodSearchResult, NutritionAction
from app.planning.schemas import (
    DailyTarget,
    MealCompositionResult,
    ManagedRecipeCandidate,
    MealSlot,
    PlanValidationAction,
    PlanValidationResult,
    PlannedMeal,
    PlanningNutritionValues,
    PlanningProfileInput,
    PreferenceReview,
    TargetCalculationResult,
    TargetRange,
)


def _profile() -> PlanningProfileInput:
    return PlanningProfileInput.model_validate(
        {
            "height_cm": "170",
            "weight_kg": "65",
            "age_years": 30,
            "formula_variant": "mifflin_st_jeor_female",
            "activity_level": "moderate",
            "goal": "loss",
            "goal_speed": "gradual_loss",
        }
    )


def _preferences(*, confirmed: bool = True) -> PreferenceReview:
    return PreferenceReview(
        confirmed=confirmed,
        exclusions=("花生",),
        taste_preferences=("清淡",),
    )


def _target() -> DailyTarget:
    return DailyTarget(
        energy_kcal=TargetRange(lower=Decimal("1700"), upper=Decimal("1900")),
        carbohydrate_g=TargetRange(lower=Decimal("190"), upper=Decimal("300")),
        protein_g=TargetRange(lower=Decimal("50"), upper=Decimal("130")),
        fat_g=TargetRange(lower=Decimal("40"), upper=Decimal("70")),
    )


def _meal(slot: MealSlot, name: str) -> PlannedMeal:
    return PlannedMeal(
        slot=slot,
        recipe_id=uuid.uuid4(),
        display_name=name,
        portion_description="一份",
        portion_grams=Decimal("100"),
        method_tags=("快手",),
        flavour_tags=("清淡",),
        matched_preference_summaries=("偏好：清淡",),
        matched_exclusion_summaries=(),
        nutrients=PlanningNutritionValues(
            energy_kcal=Decimal("600"),
            protein_g=Decimal("30"),
            fat_g=Decimal("20"),
            carbohydrate_g=Decimal("70"),
        ),
    )


class FakePlanningTools(PlanningToolAdapter):
    """A narrow graph-port fake; graph tests must not reach services or repositories."""

    def __init__(
        self,
        *,
        composition_action: PlanValidationAction = PlanValidationAction.PASS,
        validation_action: PlanValidationAction = PlanValidationAction.PASS,
    ) -> None:
        self.target_calls = 0
        self.compose_calls = 0
        self.validate_calls = 0
        self.validated_meals: list[tuple[PlannedMeal, ...]] = []
        self.upsert_calls: list[tuple[uuid.UUID, PlanningProfileInput, str]] = []
        self.capture_calls: list[tuple[uuid.UUID, uuid.UUID, str]] = []
        self.replacement_calls: list[tuple[MealSlot, str]] = []
        self.selected_food_calls: list[tuple[uuid.UUID | None, str | None]] = []
        self.replaceable_food_identities: set[tuple[uuid.UUID, str]] | None = None
        self.recipe_options: tuple[ManagedRecipeCandidate, ...] | None = None
        self.selected_recipe_calls = []
        self.search_result: FoodSearchResult | None = None
        self._composition_action = composition_action
        self._validation_action = validation_action

    async def search_food_catalog(self, request: object) -> FoodSearchResult:
        if self.search_result is None:
            raise AssertionError(f"unexpected planning food search: {request!r}")
        return self.search_result

    def keep_replaceable_food_identities(
        self,
        *,
        identities: tuple[tuple[uuid.UUID, str], ...],
        affected_slot: MealSlot,
        current_recipe_id: uuid.UUID,
        preferences: PreferenceReview,
    ) -> tuple[tuple[uuid.UUID, str], ...]:
        del affected_slot, current_recipe_id, preferences
        if self.replaceable_food_identities is None:
            return identities
        return tuple(identity for identity in identities if identity in self.replaceable_food_identities)

    def list_replacement_recipes(self, *, food_id, catalog_version, affected_slot, **_kwargs):
        if self.recipe_options is not None:
            return self.recipe_options
        return (ManagedRecipeCandidate(
            id=uuid.uuid5(food_id, "recipe"), nutrition_item_id=food_id,
            catalog_version=catalog_version, display_name="测试烤鱼", meal_slot=affected_slot,
            portion_grams=Decimal("180"), portion_description="一份", method_tags=("烤",),
            flavour_tags=("清淡",), status="enabled", revision=1,
        ),)

    def calculate_daily_target(
        self, *, profile: PlanningProfileInput, preferences: PreferenceReview
    ) -> TargetCalculationResult:
        self.target_calls += 1
        if not preferences.confirmed:
            return TargetCalculationResult(
                action=PlanValidationAction.NEEDS_INPUT,
                safe_message="请确认偏好。",
            )
        return TargetCalculationResult(
            action=PlanValidationAction.PASS,
            target=_target(),
            safe_message="目标已计算。",
        )

    def compose_daily_plan(
        self, *, user_id: uuid.UUID, target: DailyTarget, preferences: PreferenceReview, replan_count: int
    ) -> MealCompositionResult:
        self.compose_calls += 1
        if self._composition_action is not PlanValidationAction.PASS:
            return MealCompositionResult(
                action=self._composition_action,
                safe_message="没有可用候选。",
            )
        return MealCompositionResult(
            action=PlanValidationAction.PASS,
            meals=(
                _meal(MealSlot.BREAKFAST, "燕麦早餐"),
                _meal(MealSlot.LUNCH, "鸡胸肉午餐"),
                _meal(MealSlot.DINNER, "豆腐晚餐"),
            ),
            safe_message="三餐已组合。",
        )

    def validate_daily_plan(
        self, *, target: DailyTarget, meals: tuple[PlannedMeal, ...], allow_target_relaxation: bool
    ) -> PlanValidationResult:
        self.validate_calls += 1
        self.validated_meals.append(meals)
        return PlanValidationResult(
            action=self._validation_action,
            rule_id="planning-validation-pass",
            relaxed_metric="energy_or_macro" if self._validation_action is PlanValidationAction.RELAX else None,
            safe_message="餐单已校验。",
        )

    def upsert_planning_profile(
        self, *, user_id: uuid.UUID, profile: PlanningProfileInput, command_key: str
    ) -> None:
        self.upsert_calls.append((user_id, profile, command_key))

    def capture_explicit_preferences(
        self, *, user_id: uuid.UUID, run_id: uuid.UUID, statement: str
    ) -> tuple[object, ...]:
        self.capture_calls.append((user_id, run_id, statement))
        return ()

    def replace_planning_slot(
        self,
        *,
        user_id: uuid.UUID,
        target: DailyTarget,
        preferences: PreferenceReview,
        existing_meals: tuple[PlannedMeal, ...],
        affected_slot: MealSlot,
        feedback_intent: str,
        selected_food_id: uuid.UUID | None = None,
        selected_catalog_version: str | None = None,
        selected_recipe_id: uuid.UUID | None = None,
        selected_recipe_revision: int | None = None,
        replan_count: int,
    ) -> MealCompositionResult:
        self.replacement_calls.append((affected_slot, feedback_intent))
        self.selected_food_calls.append((selected_food_id, selected_catalog_version))
        self.selected_recipe_calls.append((selected_recipe_id, selected_recipe_revision))
        replacement = _meal(MealSlot.LUNCH, "清淡鸡丝午餐")
        return MealCompositionResult(
            action=PlanValidationAction.PASS,
            meals=tuple(
                replacement if meal.slot is affected_slot else meal for meal in existing_meals
            ),
            safe_message="午餐已按明确反馈替换。",
        )


def _state(*, preferences: PreferenceReview | None = None, save_profile: bool = False) -> DietPlanningState:
    return DietPlanningState(
        user_id=uuid.uuid4(),
        thread_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        command_key="diet-plan-command-key-0001",
        profile=_profile(),
        preferences=preferences or _preferences(),
        save_profile=save_profile,
        graph_version="diet-planning-graph.v1",
        prompt_version="diet-planning-command.v1",
        tool_version="planning-tools.v1",
        next_action=DietPlanningAction.READ_CONTEXT,
    )


def test_confirmed_profile_runs_only_through_tools_and_returns_exactly_three_safe_slots() -> None:
    tools = FakePlanningTools()
    state = _state(save_profile=True)

    completed = asyncio.run(DietPlanningGraph(tools=tools).ainvoke(state))

    assert completed.status.value == "completed"
    assert completed.report is not None
    assert tuple(meal["slot"] for meal in completed.report["meals"]) == (
        "breakfast",
        "lunch",
        "dinner",
    )
    assert tools.target_calls == tools.compose_calls == tools.validate_calls == 1
    assert [meal.display_name for meal in tools.validated_meals[0]] == [
        "燕麦早餐", "鸡胸肉午餐", "豆腐晚餐"
    ]
    assert tools.upsert_calls == [(state.user_id, state.profile, state.command_key)]
    import json

    serialized = json.dumps(completed.report, ensure_ascii=False)
    for forbidden in ("prompt", "provider", "candidate", "tool_output", "cost", "recipe_id"):
        assert forbidden not in serialized


def test_unconfirmed_preferences_stop_before_target_or_recipe_calls_and_never_persist_profile() -> None:
    tools = FakePlanningTools()

    waiting = asyncio.run(DietPlanningGraph(tools=tools).ainvoke(
        _state(preferences=_preferences(confirmed=False), save_profile=True)
    ))

    assert waiting.status.value == "waiting_input"
    assert waiting.report == {"stage": "needs_input", "message": "请确认本次资料与饮食偏好后继续。"}
    assert tools.target_calls == tools.compose_calls == tools.validate_calls == 0
    assert tools.upsert_calls == []


def test_deterministic_composition_failure_stops_without_identical_retries() -> None:
    tools = FakePlanningTools(composition_action=PlanValidationAction.REPLAN)

    stopped = asyncio.run(DietPlanningGraph(tools=tools).ainvoke(_state()))

    assert stopped.status.value == "limit_reached"
    assert stopped.replan_count == 0
    assert tools.compose_calls == 1
    assert tools.validate_calls == 0
    assert stopped.report == {"stage": "needs_input", "message": "没有可用候选。"}


def test_hard_validation_failure_is_not_recomputed_or_relaxed() -> None:
    tools = FakePlanningTools(validation_action=PlanValidationAction.REPLAN)
    stopped = asyncio.run(DietPlanningGraph(tools=tools).ainvoke(_state()))
    assert stopped.status.value == "limit_reached"
    assert tools.compose_calls == tools.validate_calls == 1
    assert stopped.report == {"stage": "needs_input", "message": "餐单已校验。"}


def test_initial_target_relaxation_completes_with_a_public_deviation() -> None:
    tools = FakePlanningTools(validation_action=PlanValidationAction.RELAX)

    completed = asyncio.run(DietPlanningGraph(tools=tools).ainvoke(_state()))

    assert completed.status.value == "completed"
    assert completed.report is not None
    assert completed.report["stage"] == "complete"
    assert set(completed.report["relaxation"]) == {
        "metric", "original_range", "plan_value", "deviation", "reason"
    }


def test_planning_and_meal_checkpoints_use_incompatible_versioned_codecs() -> None:
    planning = _state()

    with pytest.raises(ValidationError):
        MealAgentState.model_validate(planning.model_dump(mode="json"))
    with pytest.raises(ValidationError):
        DietPlanningState.model_validate(
            MealAgentState(
                user_id=uuid.uuid4(),
                thread_id=uuid.uuid4(),
                run_id=uuid.uuid4(),
                messages=("米饭 100 克",),
                graph_version="meal-agent-graph.v1",
                prompt_version="reasoning-parse.v1",
                tool_version="nutrition-tools-v1",
            ).model_dump(mode="json")
        )


def test_explicit_lunch_feedback_replaces_only_lunch_and_captures_once() -> None:
    tools = FakePlanningTools()
    original = asyncio.run(DietPlanningGraph(tools=tools).ainvoke(_state()))

    adjusted = asyncio.run(
        DietPlanningGraph(tools=tools).ainvoke(
            original, resume={"feedback": "午餐换清淡一些"}
        )
    )

    assert adjusted.status.value == "completed"
    assert [meal.display_name for meal in adjusted.meals] == [
        "燕麦早餐",
        "清淡鸡丝午餐",
        "豆腐晚餐",
    ]
    assert adjusted.preferences.exclusions == ("花生",)
    assert tools.replacement_calls == [(MealSlot.LUNCH, "lighter")]
    assert tools.capture_calls == [(original.user_id, original.run_id, "午餐换清淡一些")]
    assert adjusted.report is not None
    assert adjusted.report["adjustment"] == {
        "changed_slots": ["lunch"],
        "matched_constraint": "清淡",
        "range_status": adjusted.report["adjustment"]["range_status"],
    }

    replay = asyncio.run(DietPlanningGraph(tools=tools).ainvoke(adjusted))
    assert replay == adjusted
    assert len(tools.capture_calls) == 1


def test_nonexact_planning_substitution_waits_then_passes_only_offered_identity() -> None:
    tools = FakePlanningTools()
    food_id = uuid.uuid4()
    food = FoodSearchCandidate(
        food_id=food_id, canonical_name="番茄炒蛋", catalog_version="catalog-v1", prepared_state="熟制",
        source_name="测试目录", relation=FoodRelation.NAME_VARIANT,
    )
    tools.search_result = FoodSearchResult.model_construct(action=NutritionAction.ASK, query="西红柿炒鸡蛋", selected_food=None, candidates=(food,), safe_message="选择")
    original = asyncio.run(DietPlanningGraph(tools=tools).ainvoke(_state()))
    waiting = asyncio.run(DietPlanningGraph(tools=tools).ainvoke(original, resume={"feedback": "午餐换成西红柿炒鸡蛋"}))

    assert waiting.status.value == "waiting_input"
    assert waiting.pending_adjustment_slot is MealSlot.LUNCH
    assert waiting.pending_food_query == "西红柿炒鸡蛋"
    assert waiting.pending_food_candidates[0].food_id == food_id
    assert "score" not in str(waiting.report)
    completed = asyncio.run(DietPlanningGraph(tools=tools).ainvoke(waiting, resume={"candidate_id": str(food_id), "catalog_version": "catalog-v1"}))

    assert completed.status.value == "completed"
    assert tools.selected_food_calls[-1] == (food_id, "catalog-v1")


def test_planning_text_adapter_accepts_only_an_offered_candidate_identity(monkeypatch) -> None:
    tools = FakePlanningTools()
    food_id = uuid.uuid4()
    food = FoodSearchCandidate(
        food_id=food_id, canonical_name="番茄炒蛋", catalog_version="catalog-v1", prepared_state="熟制",
        source_name="测试目录", relation=FoodRelation.NAME_VARIANT,
    )
    tools.search_result = FoodSearchResult.model_construct(action=NutritionAction.ASK, query="西红柿炒鸡蛋", selected_food=None, candidates=(food,), safe_message="选择")
    original = asyncio.run(DietPlanningGraph(tools=tools).ainvoke(_state()))
    waiting = asyncio.run(DietPlanningGraph(tools=tools).ainvoke(original, resume={"feedback": "午餐换成西红柿炒鸡蛋"}))

    async def load(**_kwargs):
        return waiting

    monkeypatch.setattr(AgentService, "_load_checkpoint", staticmethod(load))
    service = AgentService(repository=object())
    text = json.dumps({"candidate_id": str(food_id), "catalog_version": "catalog-v1"})
    payload = asyncio.run(service.resume_payload_for_text(checkpointer=object(), thread_id=waiting.thread_id, text=text, graph_kind=AgentGraphKind.DIET_PLANNING))
    invalid = asyncio.run(service.resume_payload_for_text(checkpointer=object(), thread_id=waiting.thread_id, text=json.dumps({"candidate_id": str(food_id), "catalog_version": "catalog-v1", "score": 1}), graph_kind=AgentGraphKind.DIET_PLANNING))

    assert payload == {"candidate_id": str(food_id), "catalog_version": "catalog-v1"}
    assert invalid is None


def test_planning_substitution_hides_catalog_hits_without_an_enabled_recipe_for_the_slot() -> None:
    tools = FakePlanningTools()
    food_id = uuid.uuid4()
    food = FoodSearchCandidate(
        food_id=food_id, canonical_name="辣椒炒肉", catalog_version="catalog-v1", prepared_state="熟制",
        source_name="测试目录", relation=FoodRelation.SAME_CLASS,
    )
    tools.search_result = FoodSearchResult.model_construct(action=NutritionAction.ASK, query="西红柿炒鸡蛋", selected_food=None, candidates=(food,), safe_message="选择")
    tools.replaceable_food_identities = set()
    original = asyncio.run(DietPlanningGraph(tools=tools).ainvoke(_state()))

    waiting = asyncio.run(DietPlanningGraph(tools=tools).ainvoke(original, resume={"feedback": "午餐换成西红柿炒鸡蛋"}))

    assert waiting.status.value == "waiting_input"
    assert waiting.pending_food_candidates == ()
    assert waiting.report == {
        "stage": "needs_input",
        "message": "没有找到支持午餐的已启用菜谱，请更换菜名或先在菜谱管理中新增。",
    }


def test_ambiguous_feedback_requires_a_closed_three_slot_choice_and_invalid_resume_is_noop() -> None:
    tools = FakePlanningTools()
    original = asyncio.run(DietPlanningGraph(tools=tools).ainvoke(_state()))

    waiting = asyncio.run(
        DietPlanningGraph(tools=tools).ainvoke(original, resume={"feedback": "换清淡"})
    )

    assert waiting.status.value == "waiting_input"
    assert waiting.report == {
        "stage": "needs_input",
        "message": "请选择要调整的餐次。",
        "input_choices": ["breakfast", "lunch", "dinner"],
    }
    invalid = asyncio.run(
        DietPlanningGraph(tools=tools).ainvoke(waiting, resume={"slot": "snack"})
    )
    assert invalid is waiting
    assert tools.replacement_calls == []


def test_adjustment_relaxes_only_energy_or_macro_and_fourth_command_skips_composition() -> None:
    tools = FakePlanningTools()
    original = asyncio.run(DietPlanningGraph(tools=tools).ainvoke(_state()))
    current = original

    for _ in range(3):
        current = asyncio.run(
            DietPlanningGraph(tools=tools).ainvoke(
                current, resume={"feedback": "午餐换清淡一些"}
            )
        )

    assert current.status.value == "completed"
    assert current.replan_count == 3
    assert current.report is not None
    assert current.report["adjustment"]["changed_slots"] == ["lunch"]
    calls_before_fourth = len(tools.replacement_calls)
    fourth = asyncio.run(
        DietPlanningGraph(tools=tools).ainvoke(
            current, resume={"feedback": "午餐换清淡一些"}
        )
    )
    assert fourth.status.value == "limit_reached"
    assert fourth.report == {
        "stage": "needs_input",
        "code": "LIMIT_REACHED",
        "message": "本次计划已达到三次调整上限；请新建计划或修改资料与目标。",
    }
    assert len(tools.replacement_calls) == calls_before_fourth


def test_relaxation_projection_contains_only_energy_or_macro_range_details() -> None:
    initial_tools = FakePlanningTools()
    original = asyncio.run(DietPlanningGraph(tools=initial_tools).ainvoke(_state()))
    adjusting_tools = FakePlanningTools(validation_action=PlanValidationAction.RELAX)

    adjusted = asyncio.run(
        DietPlanningGraph(tools=adjusting_tools).ainvoke(
            original, resume={"feedback": "午餐换清淡一些"}
        )
    )

    assert adjusted.report is not None
    relaxation = adjusted.report["adjustment"]["relaxation"]
    assert relaxation["metric"] in {"energy_kcal", "carbohydrate_g", "protein_g", "fat_g"}
    assert set(relaxation) == {"metric", "original_range", "plan_value", "deviation", "reason"}


def _recipe_waiting_state():
    tools = FakePlanningTools()
    food_id = uuid.uuid4()
    candidate = FoodSearchCandidate(food_id=food_id, canonical_name="烤鱼", catalog_version="catalog-v1", source_name="测试目录", relation=FoodRelation.NAME_VARIANT)
    tools.search_result = FoodSearchResult.model_construct(action=NutritionAction.ASK, query="烤鱼", selected_food=None, candidates=(candidate,), safe_message="选择")
    first = tools.list_replacement_recipes(food_id=food_id, catalog_version="catalog-v1", affected_slot=MealSlot.LUNCH)[0]
    second = first.model_copy(update={"id": uuid.uuid4(), "portion_grams": Decimal("200"), "method_tags": ("蒸",)})
    tools.recipe_options = (first, second)
    graph = DietPlanningGraph(tools=tools)
    original = asyncio.run(graph.ainvoke(_state()))
    food_wait = asyncio.run(graph.ainvoke(original, resume={"feedback": "午餐换成烤鱼"}))
    recipe_wait = asyncio.run(graph.ainvoke(food_wait, resume={"candidate_id": str(food_id), "catalog_version": "catalog-v1"}))
    return tools, original, recipe_wait


def test_multiple_recipes_wait_without_composition_then_restore_and_replace_selected_recipe():
    tools, original, waiting = _recipe_waiting_state()
    assert waiting.report["stage"] == "recipe_clarification"
    assert len(waiting.pending_recipe_candidates) == 2
    assert waiting.meals == original.meals
    assert waiting.preferences == original.preferences
    assert waiting.replan_count == original.replan_count
    assert tools.replacement_calls == []
    restored = DietPlanningState.model_validate_json(waiting.model_dump_json())
    chosen = restored.pending_recipe_candidates[1]
    completed = asyncio.run(DietPlanningGraph(tools=tools).ainvoke(restored, resume={"recipe_id": str(chosen.recipe_id), "recipe_revision": chosen.revision}))
    assert tools.selected_recipe_calls == [(chosen.recipe_id, chosen.revision)]
    assert completed.meals[0] == original.meals[0]
    assert completed.meals[2] == original.meals[2]
    assert completed.preferences == original.preferences
    assert completed.replan_count == original.replan_count + 1
    assert completed.pending_recipe_candidates == ()


@pytest.mark.parametrize("change", ["unknown", "revision", "disabled", "updated"])
def test_recipe_selection_rejects_unoffered_or_changed_recipe(change):
    tools, original, waiting = _recipe_waiting_state()
    chosen = waiting.pending_recipe_candidates[0]
    payload = {"recipe_id": str(chosen.recipe_id), "recipe_revision": chosen.revision}
    if change == "unknown":
        payload["recipe_id"] = str(uuid.uuid4())
    elif change == "revision":
        payload["recipe_revision"] = 99
    elif change == "disabled":
        tools.recipe_options = ()
    else:
        tools.recipe_options = (tools.recipe_options[0].model_copy(update={"revision": 2}),)
    result = asyncio.run(DietPlanningGraph(tools=tools).ainvoke(waiting, resume=payload))
    assert tools.replacement_calls == []
    assert result.meals == original.meals
    assert result.replan_count == original.replan_count
    if change == "updated":
        assert result.pending_recipe_candidates[0].revision == 2
    if change == "disabled":
        assert result.pending_recipe_candidates == ()
        assert result.report["stage"] == "needs_input"


def test_recipe_selection_text_contract_rejects_internal_fields_and_boolean_revision(monkeypatch):
    _, _, waiting = _recipe_waiting_state()
    async def load(**_kwargs):
        return waiting
    monkeypatch.setattr(AgentService, "_load_checkpoint", staticmethod(load))
    service = AgentService(repository=object())
    chosen = waiting.pending_recipe_candidates[0]
    payload = {"recipe_id": str(chosen.recipe_id), "recipe_revision": chosen.revision}
    def parse(value):
        return asyncio.run(service.resume_payload_for_text(checkpointer=object(), thread_id=waiting.thread_id, text=json.dumps(value), graph_kind=AgentGraphKind.DIET_PLANNING))
    assert parse(payload) == payload
    assert parse({**payload, "food_id": str(chosen.food_id)}) is None
    assert parse({**payload, "recipe_revision": True}) is None


def test_temporary_adjustment_preferences_are_applied_to_the_current_plan_once() -> None:
    from app.agent.tools import CapturedPreferenceSummary

    class TemporaryTools(FakePlanningTools):
        def capture_explicit_preferences(self, *, user_id, run_id, statement):
            self.capture_calls.append((user_id, run_id, statement))
            return (
                CapturedPreferenceSummary(category="avoidance", canonical_text="不吃辣", scope="current_plan"),
                CapturedPreferenceSummary(category="stable_preference", canonical_text="清淡", scope="current_plan"),
            )

        def replace_planning_slot(self, **kwargs):
            assert kwargs["preferences"].exclusions == ("花生", "辣")
            assert kwargs["preferences"].taste_preferences == ("清淡",)
            return super().replace_planning_slot(**kwargs)

    tools = TemporaryTools()
    graph = DietPlanningGraph(tools=tools)
    original = asyncio.run(graph.ainvoke(_state()))
    adjusted = asyncio.run(graph.ainvoke(original, resume={"feedback": "今天午餐换清淡一些，不吃辣"}))
    assert adjusted.status.value == "completed"
    assert len(tools.capture_calls) == 1
    assert original.preferences.exclusions == ("花生",)
    assert asyncio.run(graph.ainvoke(adjusted)) == adjusted
    assert len(tools.capture_calls) == 1


def test_range_relaxation_reuses_meals_without_spending_adjustment_count():
    class RangeMissTools(FakePlanningTools):
        def validate_daily_plan(self, *, target, meals, allow_target_relaxation):
            self.validate_calls += 1
            self.validated_meals.append(meals)
            return PlanValidationResult(
                action=PlanValidationAction.RELAX if allow_target_relaxation else PlanValidationAction.REPLAN,
                rule_id="energy_kcal-target-relaxation" if allow_target_relaxation else "energy_kcal-out-of-range",
                relaxed_metric="energy_kcal" if allow_target_relaxation else None,
                relaxation_available=not allow_target_relaxation,
                safe_message="能量目标存在偏差。",
            )
    tools = RangeMissTools()
    completed = asyncio.run(DietPlanningGraph(tools=tools).ainvoke(_state()))
    assert completed.status.value == "completed"
    assert completed.replan_count == 0
    assert tools.compose_calls == 1
    assert tools.validate_calls == 2
    assert tools.validated_meals[0] is tools.validated_meals[1]
    assert "能量目标存在偏差" in str(completed.report)


def test_exhausted_tool_budget_stops_before_another_domain_call():
    tools = FakePlanningTools()
    state = _state()
    state = state.model_copy(update={"budget": state.budget.model_copy(update={"tool_calls": 12})})
    stopped = asyncio.run(DietPlanningGraph(tools=tools).ainvoke(state))
    assert stopped.status.value == "limit_reached"
    assert tools.target_calls == tools.compose_calls == tools.validate_calls == 0


@pytest.mark.parametrize("rule", ["confirmed-exclusion", "minimum-plan-energy-floor", "fat_g-ratio-out-of-range"])
def test_hard_constraint_cannot_offer_relaxation(rule):
    with pytest.raises(ValidationError, match="only target range"):
        PlanValidationResult(action=PlanValidationAction.REPLAN, rule_id=rule, relaxation_available=True, safe_message="不可放宽。")
