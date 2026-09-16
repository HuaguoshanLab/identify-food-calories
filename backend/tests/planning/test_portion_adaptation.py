"""Portion changes use catalog calculations; target relaxation is bounded in every metric."""

from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.planning.schemas import MealSlot, PlanValidationAction, PreferenceReview, REQUIRED_MEAL_SLOTS, TargetRange
from app.planning.selection import MealSelectionPolicy, PlanningSearchBudget
from app.planning.service import PlanningService
from tests.planning.test_personalized_selection import candidate, food, target
from tests.planning.test_planning_service import FakePlanningRepository, RecipeNutritionPort, controlled_recipe, valid_daily_meals, validation_target


class RecordingNutrition(RecipeNutritionPort):
    def __init__(self, foods):
        super().__init__(foods)
        self.requests = []

    def calculate_nutrition(self, request):
        self.requests.append(request)
        return super().calculate_nutrition(request)


def service_pool(*, managed=True, policy=None, budget=None):
    foods = [food(slot.value) for slot in REQUIRED_MEAL_SLOTS]
    rows = [candidate(slot, item) if managed else controlled_recipe(slot=slot, food=item, name=item.canonical_name)
            for slot, item in zip(REQUIRED_MEAL_SLOTS, foods, strict=True)]
    repo = FakePlanningRepository(candidates=rows) if managed else FakePlanningRepository(recipes=rows)
    port = RecordingNutrition(foods)
    return PlanningService(repository=repo, nutrition_port=port, selection_policy=policy, search_budget=budget), port, rows


@pytest.mark.parametrize("managed", [True, False])
def test_adjusted_portions_are_recalculated_from_catalog_and_original_rows_are_unchanged(managed):
    service, port, rows = service_pool(managed=managed)
    originals = [row.model_dump() for row in rows]
    result = service.compose_daily_meals(catalog_version=None, target=target("1800"), preferences=PreferenceReview(confirmed=True))
    assert [meal.portion_grams for meal in result.meals] == [75, 120, 105]
    assert [meal.nutrients.energy_kcal for meal in result.meals] == [450, 720, 630]
    assert [row.model_dump() for row in rows] == originals
    assert [request.grams for request in port.requests] == [100, 75, 100, 120, 100, 105]
    assert all("原份量 100g" in meal.portion_description for meal in result.meals)
    assert service.validate_plan(target=target("1800"), meals=result.meals).action is PlanValidationAction.PASS


def test_single_replacement_subtracts_snack_and_preserves_fixed_snapshots():
    service, _, _ = service_pool()
    initial = service.compose_daily_meals(catalog_version=None, target=target("1800"), preferences=PreferenceReview(confirmed=True)).meals
    snack = initial[0].model_copy(update={"slot": MealSlot.SNACK, "recipe_id": uuid4(),
                                        "nutrients": initial[0].nutrients.model_copy(update={"energy_kcal": Decimal(120)})})
    fixed = (initial[0], initial[2], snack)
    result = service.compose_daily_meals(catalog_version=None, target=target("1800"), preferences=PreferenceReview(confirmed=True), required_slot=MealSlot.LUNCH, fixed_meals=fixed)
    assert result.meals[0] is fixed[0] and result.meals[2] is fixed[1] and result.meals[3] is fixed[2]
    assert result.meals[1].portion_grams == 100
    assert sum(meal.nutrients.energy_kcal for meal in result.meals) == 1800


@pytest.mark.parametrize(("energy", "expected"), [("5000", [125, 125, 125]), ("1200", [75, 80, 75])])
def test_adjustments_stay_within_original_portion_bounds(energy, expected):
    service, port, _ = service_pool()
    service.compose_daily_meals(catalog_version=None, target=target(energy), preferences=PreferenceReview(confirmed=True))
    assert [request.grams for request in port.requests][1::2] == expected
    assert all(75 <= request.grams <= 125 for request in port.requests)


def test_disable_portions_restores_original_calculations_and_missing_target_does_not_scale():
    for policy, daily_target in [(MealSelectionPolicy(portion_adjustment_enabled=False), target("1800")), (None, None)]:
        service, port, rows = service_pool(policy=policy)
        result = service.compose_daily_meals(catalog_version=None, target=daily_target, preferences=PreferenceReview(confirmed=True))
        assert [request.grams for request in port.requests] == [100, 100, 100]
        assert [meal.portion_description for meal in result.meals] == [row.portion_description for row in rows]


def test_variants_share_candidate_and_combination_budgets():
    service, port, _ = service_pool(budget=PlanningSearchBudget(options_per_slot=1, max_combinations=1))
    result = service.compose_daily_meals(catalog_version=None, target=target("1800"), preferences=PreferenceReview(confirmed=True))
    assert len(result.meals) == 3
    assert len(port.requests) == 6
    assert [meal.nutrients.energy_kcal for meal in result.meals] == [450, 720, 630]


def test_each_controlled_ingredient_is_recalculated_at_the_actual_portion_multiplier():
    foods = [food('食材甲'), food('食材乙')]
    recipes = []
    for slot in REQUIRED_MEAL_SLOTS:
        recipe = controlled_recipe(slot=slot, food=foods[0], name=slot.value)
        first = recipe.ingredients[0].model_copy(update={"grams": Decimal(40)})
        second = first.model_copy(update={"food_id": foods[1].id, "grams": Decimal(60)})
        recipes.append(recipe.model_copy(update={"ingredients": (first, second)}))
    port = RecordingNutrition(foods)
    service = PlanningService(repository=FakePlanningRepository(recipes=recipes), nutrition_port=port)
    result = service.compose_daily_meals(catalog_version=None, target=target("1800"), preferences=PreferenceReview(confirmed=True))
    assert [request.grams for request in port.requests] == [40, 60, 30, 45, 40, 60, 48, 72, 40, 60, 42, 63]
    assert [meal.nutrients.energy_kcal for meal in result.meals] == [450, 720, 630]


def test_unavailable_adjusted_calculation_keeps_the_original_candidate():
    from app.nutrition.schemas import NutritionAction, NutritionCalculationResult

    service, port, _ = service_pool()
    original = port.calculate_nutrition

    def calculate(request):
        if request.grams != 100:
            return NutritionCalculationResult(action=NutritionAction.BLOCK, safe_message="本份量暂不可计算。")
        return original(request)

    port.calculate_nutrition = calculate
    result = service.compose_daily_meals(catalog_version=None, target=target("1800"), preferences=PreferenceReview(confirmed=True))
    assert [meal.portion_grams for meal in result.meals] == [100, 100, 100]
    assert service.validate_plan(target=target("1800"), meals=result.meals).action is PlanValidationAction.PASS


def test_adaptation_caps_grams_and_skips_zero_energy_or_nonrepresentable_portions():
    service, _, _ = service_pool()
    meal = valid_daily_meals()[0].model_copy(update={"portion_grams": Decimal("1999.5")})
    assert service._adapted_portion(meal, target("10000"), ()) == 2000
    tiny = meal.model_copy(update={"portion_grams": Decimal("0.1")})
    assert service._adapted_portion(tiny, target("1800"), ()) is None
    no_energy = meal.model_copy(update={"nutrients": meal.nutrients.model_copy(update={"energy_kcal": Decimal(0)})})
    assert service._adapted_portion(no_energy, target("1800"), ()) is None


@pytest.mark.parametrize(("energy", "accepted"), [("1620", True), ("1619.9", False), ("2200", True), ("2200.1", False)])
def test_relaxation_checks_exact_nearest_edge_boundary(energy, accepted):
    service, _, _ = service_pool()
    factor = Decimal(energy) / 1900
    meals = tuple(meal.model_copy(update={"nutrients": meal.nutrients.model_copy(update={
        key: value * factor for key, value in meal.nutrients.model_dump().items()
    })}) for meal in valid_daily_meals())
    # Set the final energy by subtraction to avoid a recurring Decimal remainder at the boundary.
    meals = (*meals[:2], meals[2].model_copy(update={"nutrients": meals[2].nutrients.model_copy(update={
        "energy_kcal": Decimal(energy) - sum(meal.nutrients.energy_kcal for meal in meals[:2])})}))
    result = service.validate_plan(target=validation_target(), meals=meals, allow_target_relaxation=True)
    assert result.action is (PlanValidationAction.RELAX if accepted else PlanValidationAction.REPLAN)
    first = service.validate_plan(target=validation_target(), meals=meals)
    assert first.relaxation_available is accepted


def test_small_energy_miss_cannot_hide_a_large_protein_miss():
    service, _, _ = service_pool()
    daily_target = validation_target().model_copy(update={"energy_kcal": TargetRange(lower=1920, upper=2000), "protein_g": TargetRange(lower=60, upper=80)})
    result = service.validate_plan(target=daily_target, meals=valid_daily_meals(), allow_target_relaxation=True)
    assert result.rule_id == "protein_g-deviation-limit"
    assert not result.relaxation_available


def test_zero_tolerance_disables_relaxation_without_affecting_in_range_plan():
    service, _, _ = service_pool(policy=MealSelectionPolicy(max_target_deviation=0))
    assert service.validate_plan(target=validation_target(), meals=valid_daily_meals()).action is PlanValidationAction.PASS
    narrower = validation_target().model_copy(update={"energy_kcal": TargetRange(lower=1901, upper=2000)})
    assert service.validate_plan(target=narrower, meals=valid_daily_meals(), allow_target_relaxation=True).action is PlanValidationAction.REPLAN


@pytest.mark.parametrize(("name", "value"), [("portion_min_multiplier", 0), ("portion_min_multiplier", 1.1), ("portion_max_multiplier", 0.9), ("portion_max_multiplier", 2), ("max_target_deviation", -1), ("max_target_deviation", "NaN"), ("max_target_deviation", 1)])
def test_invalid_portion_and_deviation_configuration_fails_closed(name, value):
    with pytest.raises(ValidationError):
        MealSelectionPolicy(**{name: value})
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{f"planning_{name}": value})
