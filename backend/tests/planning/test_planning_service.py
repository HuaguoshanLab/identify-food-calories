"""Fake-port contracts for deterministic, non-medical diet planning."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.planning.schemas import (
    ACTIVITY_FACTORS,
    HEALTH_REFUSAL_MESSAGE,
    TARGET_POLICY_VERSION,
    ActivityLevel,
    ControlledRecipe,
    ControlledRecipeIngredient,
    DailyTarget,
    MealSlot,
    PlanValidationAction,
    PlanningProfileInput,
    PreferenceReview,
)
from app.planning.service import PlanningService
from app.nutrition.schemas import (
    NutritionAction,
    NutritionCalculationInput,
    NutritionValues,
    QualifiedFood,
)
from app.nutrition.service import NutritionService


class FakePlanningRepository:
    """Records recipe access so health guards prove they run before retrieval."""

    def __init__(self, recipes: list[ControlledRecipe] | None = None) -> None:
        self.recipe_search_calls = 0
        self.recipes = recipes or []

    def list_controlled_recipes(self, *, catalog_version: str) -> list[ControlledRecipe]:
        self.recipe_search_calls += 1
        return self.recipes


class FakeNutritionPort:
    """Deliberately unused by target calculation; a graph later owns recipe composition."""

    def calculate_recipe_nutrients(self, *, recipe_id: str, catalog_version: str) -> object:
        raise AssertionError("target calculation must not call nutrition/recipe ports")


class FakeRecipeNutritionRepository:
    """Only returns the qualified catalog fixtures explicitly supplied by the contract."""

    def __init__(self, foods: list[QualifiedFood]) -> None:
        self.foods = foods

    def search_qualified_foods(self, *, normalized_query: str, limit: int) -> list[QualifiedFood]:
        return self.foods[:limit]

    def get_qualified_food(
        self, *, food_id: uuid.UUID, catalog_version: str
    ) -> QualifiedFood | None:
        return next(
            (
                food
                for food in self.foods
                if food.id == food_id and food.catalog_version == catalog_version
            ),
            None,
        )


class RecipeNutritionPort:
    """Uses the real deterministic calculator; recipes never own nutrient totals."""

    def __init__(self, foods: list[QualifiedFood]) -> None:
        self._service = NutritionService(repository=FakeRecipeNutritionRepository(foods))

    def calculate_nutrition(self, request: NutritionCalculationInput):
        return self._service.calculate_nutrition(request)

    def calculate_recipe_nutrients(self, *, recipe_id: str, catalog_version: str) -> object:
        raise AssertionError("recipe totals must be recomputed per qualified ingredient")


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


CATALOG_VERSION = "fdc-foundation-2026-04"


def qualified_food(*, name: str, energy: str, grams: str = "100") -> QualifiedFood:
    return QualifiedFood(
        id=uuid.uuid4(),
        canonical_name=name,
        catalog_version=CATALOG_VERSION,
        prepared_state="cooked",
        source_name="Controlled test catalog",
        source_url="https://example.invalid/catalog",
        license_name="CC0 1.0",
        nutrients_per_100g=NutritionValues(
            energy_kcal=Decimal(energy),
            protein_g=Decimal("10"),
            fat_g=Decimal("2"),
            carbohydrate_g=Decimal("20"),
        ),
    )


def controlled_recipe(*, slot: MealSlot, food: QualifiedFood, name: str) -> ControlledRecipe:
    return ControlledRecipe(
        id=uuid.uuid4(),
        stable_id=f"recipe.{slot.value}.v1",
        display_name=name,
        recipe_version="controlled-recipes.v1",
        catalog_version=CATALOG_VERSION,
        meal_slots=(slot,),
        portion_description="一份",
        portion_grams=Decimal("100"),
        method_tags=("快手",),
        flavour_tags=("清淡",),
        ingredients=(
            ControlledRecipeIngredient(
                food_id=food.id,
                catalog_version=CATALOG_VERSION,
                grams=Decimal("100"),
                portion_description="一份",
            ),
        ),
        source_reference="backend/app/planning/data/controlled-recipes.v1.json",
        audited_at=datetime(2026, 9, 1, tzinfo=UTC),
        audit_version="recipe-audit.v1",
    )


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


@pytest.mark.parametrize(
    "changes",
    [
        {"source_kind": "third_party"},
        {"license_name": "CC-BY-4.0"},
        {"audit_status": "pending"},
        {"audited_by_role": "admin"},
        {"audited_at": None},
        {"source_reference": ""},
        {"recipe_version": ""},
        {"catalog_version": ""},
        {"audit_version": ""},
        {"meal_slots": ()},
        {"portion_grams": "0"},
        {"method_tags": ()},
        {"flavour_tags": ()},
    ],
)
def test_controlled_recipe_rejects_missing_or_unapproved_r03_metadata(
    changes: dict[str, object]
) -> None:
    food = qualified_food(name="测试食材", energy="100")
    recipe = controlled_recipe(slot=MealSlot.BREAKFAST, food=food, name="测试早餐")

    with pytest.raises(ValidationError):
        ControlledRecipe.model_validate({**recipe.model_dump(), **changes})


def test_controlled_recipe_rejects_catalog_mismatch_and_invalid_ingredient_portion() -> None:
    food = qualified_food(name="测试食材", energy="100")
    recipe = controlled_recipe(slot=MealSlot.BREAKFAST, food=food, name="测试早餐")

    with pytest.raises(ValidationError):
        ControlledRecipe.model_validate(
            {
                **recipe.model_dump(),
                "ingredients": [
                    {
                        **recipe.ingredients[0].model_dump(),
                        "catalog_version": "different-catalog.v1",
                    }
                ],
            }
        )
    with pytest.raises(ValidationError):
        ControlledRecipeIngredient.model_validate(
            {
                **recipe.ingredients[0].model_dump(),
                "grams": "0",
            }
        )


def test_daily_meal_candidates_have_public_d08_fields_and_catalog_recomputed_nutrition() -> None:
    breakfast_food = qualified_food(name="燕麦", energy="100")
    lunch_food = qualified_food(name="鸡胸肉", energy="150")
    dinner_food = qualified_food(name="豆腐", energy="80")
    recipes = [
        controlled_recipe(slot=MealSlot.BREAKFAST, food=breakfast_food, name="燕麦早餐"),
        controlled_recipe(slot=MealSlot.LUNCH, food=lunch_food, name="鸡胸肉午餐"),
        controlled_recipe(slot=MealSlot.DINNER, food=dinner_food, name="豆腐晚餐"),
    ]
    service = PlanningService(
        repository=FakePlanningRepository(recipes),
        nutrition_port=RecipeNutritionPort([breakfast_food, lunch_food, dinner_food]),
    )

    result = service.compose_daily_meals(
        catalog_version=CATALOG_VERSION,
        preferences=confirmed_preferences(),
    )

    assert result.action is PlanValidationAction.PASS
    assert tuple(meal.slot for meal in result.meals) == (
        MealSlot.BREAKFAST,
        MealSlot.LUNCH,
        MealSlot.DINNER,
    )
    assert tuple(meal.display_name for meal in result.meals) == ("燕麦早餐", "鸡胸肉午餐", "豆腐晚餐")
    assert all(meal.portion_description == "一份" for meal in result.meals)
    assert all(meal.portion_grams == Decimal("100") for meal in result.meals)
    assert all(meal.method_tags == ("快手",) for meal in result.meals)
    assert all(meal.flavour_tags == ("清淡",) for meal in result.meals)
    assert all(meal.matched_preference_summaries == ("偏好：清淡",) for meal in result.meals)
    assert all(meal.matched_exclusion_summaries == () for meal in result.meals)
    assert tuple(meal.nutrients.energy_kcal for meal in result.meals) == (
        Decimal("100"),
        Decimal("150"),
        Decimal("80"),
    )


def test_composition_rejects_nonqualified_catalog_food_and_never_uses_stored_recipe_total() -> None:
    food = qualified_food(name="未合格食材", energy="999")
    recipe = controlled_recipe(slot=MealSlot.BREAKFAST, food=food, name="不能使用的早餐")
    repository = FakePlanningRepository([recipe])
    service = PlanningService(
        repository=repository,
        nutrition_port=RecipeNutritionPort([]),
    )

    result = service.compose_daily_meals(
        catalog_version=CATALOG_VERSION,
        preferences=confirmed_preferences(),
    )

    assert result.action is PlanValidationAction.REPLAN
    assert result.meals == ()
    assert result.safe_message == "没有同时满足受控来源、审核、目录资格和三餐槽位的候选。"
    with pytest.raises(ValidationError):
        ControlledRecipe.model_validate({**recipe.model_dump(), "stored_total": {"energy_kcal": "1"}})
