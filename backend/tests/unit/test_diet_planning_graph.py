"""RED contracts for the bounded, tool-only diet-planning subgraph."""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.agent.graph import DietPlanningGraph
from app.agent.state import DietPlanningAction, DietPlanningState, MealAgentState
from app.agent.tools import PlanningToolAdapter
from app.planning.schemas import (
    DailyTarget,
    MealCompositionResult,
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

    def __init__(self, *, composition_action: PlanValidationAction = PlanValidationAction.PASS) -> None:
        self.target_calls = 0
        self.compose_calls = 0
        self.validate_calls = 0
        self.upsert_calls: list[tuple[uuid.UUID, PlanningProfileInput, str]] = []
        self._composition_action = composition_action

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
        self, *, target: DailyTarget, preferences: PreferenceReview, replan_count: int
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
        self, *, target: DailyTarget, meals: tuple[PlannedMeal, ...], replan_count: int
    ) -> PlanValidationResult:
        self.validate_calls += 1
        return PlanValidationResult(
            action=PlanValidationAction.PASS,
            rule_id="planning-validation-pass",
            safe_message="餐单已校验。",
        )

    def upsert_planning_profile(
        self, *, user_id: uuid.UUID, profile: PlanningProfileInput, command_key: str
    ) -> None:
        self.upsert_calls.append((user_id, profile, command_key))


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
    assert tools.upsert_calls == [(state.user_id, state.profile, state.command_key)]
    serialized = completed.model_dump_json()
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


def test_replan_budget_stops_after_three_attempts_without_looping() -> None:
    tools = FakePlanningTools(composition_action=PlanValidationAction.REPLAN)

    stopped = asyncio.run(DietPlanningGraph(tools=tools).ainvoke(_state()))

    assert stopped.status.value == "limit_reached"
    assert stopped.replan_count == 3
    assert tools.compose_calls == 3
    assert stopped.report == {
        "stage": "needs_input",
        "message": "无法在三次调整内满足所有约束；请修改资料或新建计划。",
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
