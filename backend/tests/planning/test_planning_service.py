"""Fake-port contracts for deterministic, non-medical diet planning."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.planning.schemas import (
    ACTIVITY_FACTORS,
    HEALTH_REFUSAL_MESSAGE,
    TARGET_POLICY_VERSION,
    ActivityLevel,
    DailyTarget,
    PlanValidationAction,
    PlanningProfileInput,
    PreferenceReview,
)
from app.planning.service import PlanningService


class FakePlanningRepository:
    """Records recipe access so health guards prove they run before retrieval."""

    def __init__(self) -> None:
        self.recipe_search_calls = 0

    def list_controlled_recipes(self, *, catalog_version: str) -> list[object]:
        self.recipe_search_calls += 1
        return []


class FakeNutritionPort:
    """Deliberately unused by target calculation; a graph later owns recipe composition."""

    def calculate_recipe_nutrients(self, *, recipe_id: str, catalog_version: str) -> object:
        raise AssertionError("target calculation must not call nutrition/recipe ports")


def confirmed_preferences() -> PreferenceReview:
    return PreferenceReview(confirmed=True, exclusions=("香菜",), taste_preferences=("清淡",))


def complete_profile(**changes: object) -> PlanningProfileInput:
    values: dict[str, object] = {
        "height_cm": Decimal("170"),
        "weight_kg": Decimal("70"),
        "age_years": 30,
        "formula_variant": "mifflin_st_jeor_male",
        "activity_level": ActivityLevel.MODERATE,
        "goal": "maintain",
        "goal_speed": "maintain",
    }
    values.update(changes)
    return PlanningProfileInput.model_validate(values)


def test_target_policy_has_versioned_decimal_mifflin_and_amdr_ranges() -> None:
    service = PlanningService(
        repository=FakePlanningRepository(), nutrition_port=FakeNutritionPort()
    )

    result = service.calculate_daily_target(complete_profile(), confirmed_preferences())

    assert result.action is PlanValidationAction.PASS
    assert result.target is not None
    assert result.target.policy_version == TARGET_POLICY_VERSION
    assert result.target.formula_version == "mifflin-st-jeor.v1"
    assert result.target.energy_kcal.lower == Decimal("2407.125")
    assert result.target.energy_kcal.upper == Decimal("2607.125")
    assert result.target.carbohydrate_g.lower == Decimal("270.8015625")
    assert result.target.carbohydrate_g.upper == Decimal("423.6578125")
    assert result.target.protein_g.lower == Decimal("60.178125")
    assert result.target.protein_g.upper == Decimal("228.1234375")
    assert result.target.fat_g.lower == Decimal("53.49166666666666666666666667")
    assert result.target.fat_g.upper == Decimal("101.3881944444444444444444444")


@pytest.mark.parametrize(
    ("activity", "factor"),
    [
        (ActivityLevel.SEDENTARY, Decimal("1.20")),
        (ActivityLevel.LIGHT, Decimal("1.375")),
        (ActivityLevel.MODERATE, Decimal("1.55")),
        (ActivityLevel.HIGH, Decimal("1.725")),
        (ActivityLevel.VERY_HIGH, Decimal("1.90")),
    ],
)
def test_activity_factors_are_the_five_frozen_target_policy_values(
    activity: ActivityLevel, factor: Decimal
) -> None:
    assert ACTIVITY_FACTORS[activity] == factor


@pytest.mark.parametrize(
    ("profile", "preferences"),
    [
        (complete_profile(height_cm=None), confirmed_preferences()),
        (complete_profile(formula_variant=None), confirmed_preferences()),
        (complete_profile(activity_level=None), confirmed_preferences()),
        (complete_profile(goal=None), confirmed_preferences()),
        (complete_profile(goal_speed=None), confirmed_preferences()),
        (complete_profile(), PreferenceReview(confirmed=False)),
    ],
)
def test_incomplete_profile_or_unconfirmed_preferences_needs_input_before_calculation(
    profile: PlanningProfileInput, preferences: PreferenceReview
) -> None:
    repository = FakePlanningRepository()
    result = PlanningService(
        repository=repository, nutrition_port=FakeNutritionPort()
    ).calculate_daily_target(profile, preferences)

    assert result.action is PlanValidationAction.NEEDS_INPUT
    assert result.target is None
    assert repository.recipe_search_calls == 0


@pytest.mark.parametrize(
    "profile",
    [
        complete_profile(age_years=18),
        complete_profile(age_years=79),
        complete_profile(is_pregnant_or_breastfeeding=True),
        complete_profile(has_disease_or_treatment=True),
        complete_profile(uses_medication=True),
        complete_profile(has_eating_disorder_or_self_harm_risk=True),
        complete_profile(goal_speed="faster_loss"),
        complete_profile(height_cm=Decimal("130"), weight_kg=Decimal("25"), age_years=78),
    ],
)
def test_health_scope_guards_block_before_recipe_port_access(profile: PlanningProfileInput) -> None:
    repository = FakePlanningRepository()
    result = PlanningService(
        repository=repository, nutrition_port=FakeNutritionPort()
    ).calculate_daily_target(profile, confirmed_preferences())

    assert result.action is PlanValidationAction.BLOCK_HEALTH_SCOPE
    assert result.target is None
    assert result.safe_message == HEALTH_REFUSAL_MESSAGE
    assert repository.recipe_search_calls == 0


def test_plan_validation_actions_are_closed_and_relax_never_accepts_exclusions() -> None:
    assert {action.value for action in PlanValidationAction} == {
        "PASS",
        "REPLAN",
        "RELAX",
        "BLOCK_HEALTH_SCOPE",
        "NEEDS_INPUT",
    }

    target = DailyTarget.model_validate(
        {
            "energy_kcal": {"lower": "1800", "upper": "2000"},
            "carbohydrate_g": {"lower": "202.5", "upper": "325"},
            "protein_g": {"lower": "45", "upper": "175"},
            "fat_g": {"lower": "40", "upper": "77.8"},
        }
    )
    result = PlanningService(
        repository=FakePlanningRepository(), nutrition_port=FakeNutritionPort()
    ).validate_plan(target=target, matched_exclusions=("香菜",), allow_target_relaxation=True)

    assert result.action is PlanValidationAction.REPLAN
    assert result.safe_message == "受控餐单包含已确认的排除项，不能放宽该约束。"


def test_public_dtos_are_frozen_and_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        PlanningProfileInput.model_validate({"height_cm": "170", "unknown": True})
    with pytest.raises(ValidationError):
        DailyTarget.model_validate({"unexpected": True})
