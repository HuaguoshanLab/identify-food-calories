"""Explicit components must not escape via generation or replacement paths."""
import pytest

from app.planning.schemas import MealSlot, PreferenceReview, PlanValidationAction
from app.planning.service import PlanningService
from tests.planning.test_planning_service import FakePlanningRepository, RecipeNutritionPort, managed_candidate, qualified_food


@pytest.mark.parametrize("role", ["staple", "protein", "vegetable", "side", "drink"])
def test_components_never_become_standalone_meals_even_with_a_permissive_repository(role):
    food = qualified_food(name="不根据名称推断", energy="200")
    rows = [managed_candidate(slot=slot, food=food).model_copy(update={"meal_role": role}) for slot in (MealSlot.BREAKFAST, MealSlot.LUNCH, MealSlot.DINNER)]
    service = PlanningService(repository=FakePlanningRepository(candidates=rows), nutrition_port=RecipeNutritionPort([food]))
    preferences = PreferenceReview(confirmed=True)
    result = service.compose_daily_meals(catalog_version=None, preferences=preferences)
    assert result.action is PlanValidationAction.REPLAN and not result.meals
    assert service.list_replacement_recipes(food_id=food.id, catalog_version=food.catalog_version, affected_slot=MealSlot.LUNCH, exclude_recipe_ids=(), preferences=preferences) == ()
    assert service.keep_replaceable_food_identities(identities=((food.id, food.catalog_version),), affected_slot=MealSlot.LUNCH, exclude_recipe_ids=(), preferences=preferences) == ()
