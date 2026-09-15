"""Behavioral regressions for goals, exclusions and single-meal replacement."""

from decimal import Decimal
from types import SimpleNamespace
import uuid

import pytest

from app.agent.tools import SessionNutritionToolAdapter
from app.planning.schemas import (
    DailyTarget,
    MealSlot,
    PlanValidationAction,
    PreferenceReview,
    REQUIRED_MEAL_SLOTS,
)
from app.planning.selection import MAX_RECIPE_CANDIDATES
from app.planning.service import PlanningService
from tests.planning.test_planning_service import (
    FakePlanningRepository,
    RecipeNutritionPort,
    controlled_recipe,
    managed_candidate,
    qualified_food,
    validation_target,
    valid_daily_meals,
)


def food(name: str, energy: str = "600", aliases: tuple[str, ...] = ()):
    base = qualified_food(name=name, energy=energy)
    value = Decimal(energy)
    nutrients = base.nutrients_per_100g.model_copy(
        update={
            "protein_g": value * Decimal("0.20") / 4,
            "carbohydrate_g": value * Decimal("0.50") / 4,
            "fat_g": value * Decimal("0.30") / 9,
        }
    )
    return base.model_copy(update={"aliases": aliases, "nutrients_per_100g": nutrients})


def candidate(slot, item, *, flavour="清淡", name=None):
    return managed_candidate(slot=slot, food=item).model_copy(
        update={
            "portion_grams": Decimal("100"),
            "flavour_tags": (flavour,),
            "display_name": name or item.canonical_name,
        }
    )


def target(energy: str) -> DailyTarget:
    value = Decimal(energy)
    return DailyTarget.model_validate(
        {
            "energy_kcal": {"lower": value - 1, "upper": value + 1},
            "protein_g": {
                "lower": value * Decimal("0.10") / 4,
                "upper": value * Decimal("0.35") / 4,
            },
            "carbohydrate_g": {
                "lower": value * Decimal("0.45") / 4,
                "upper": value * Decimal("0.65") / 4,
            },
            "fat_g": {
                "lower": value * Decimal("0.20") / 9,
                "upper": value * Decimal("0.35") / 9,
            },
        }
    )


class ServiceTools(SessionNutritionToolAdapter):
    """Real tool adapter with a fake persistence boundary, not a scripted planner."""

    def __init__(self, service):
        self.service = service

    def _planning_service(self):
        return SimpleNamespace(close=lambda: None), self.service


def setup_pool():
    low = [food(f"{slot.value}小份") for slot in REQUIRED_MEAL_SLOTS]
    high = [food(f"{slot.value}大份", "800") for slot in REQUIRED_MEAL_SLOTS]
    small = [
        candidate(slot, item)
        for slot, item in zip(REQUIRED_MEAL_SLOTS, low, strict=True)
    ]
    large = [
        candidate(slot, item, flavour="香辣")
        for slot, item in zip(REQUIRED_MEAL_SLOTS, high, strict=True)
    ]
    repository = FakePlanningRepository(candidates=[*small, *large])
    service = PlanningService(
        repository=repository, nutrition_port=RecipeNutritionPort([*low, *high])
    )
    return service, repository, small, large


def test_actual_tool_selects_different_meals_for_different_targets_and_is_repeatable():
    service, _, small, large = setup_pool()
    tools = ServiceTools(service)
    kwargs = dict(
        user_id=uuid.uuid4(),
        preferences=PreferenceReview(confirmed=True),
        replan_count=0,
    )
    lower = tools.compose_daily_plan(target=target("1800"), **kwargs)
    higher = tools.compose_daily_plan(target=target("2400"), **kwargs)
    repeated = tools.compose_daily_plan(target=target("1800"), **kwargs)
    assert tuple(meal.recipe_id for meal in lower.meals) == tuple(
        item.id for item in small
    )
    assert tuple(meal.recipe_id for meal in higher.meals) == tuple(
        item.id for item in large
    )
    assert lower == repeated
    assert (
        service.validate_plan(target=target("1800"), meals=lower.meals).action
        is PlanValidationAction.PASS
    )


def test_recent_meals_remain_available_when_only_they_satisfy_the_target():
    service, repository, small, _ = setup_pool()
    repository.recent_recipe_ids = tuple(item.id for item in small)
    result = service.compose_daily_meals(
        user_id=uuid.uuid4(),
        catalog_version=None,
        target=target("1800"),
        preferences=PreferenceReview(confirmed=True),
    )
    assert {meal.recipe_id for meal in result.meals} == set(
        repository.recent_recipe_ids
    )


def test_preference_breaks_a_tie_between_equally_valid_plans():
    service, repository, small, _ = setup_pool()
    spicy = [
        item.model_copy(update={"id": uuid.uuid4(), "flavour_tags": ("香辣",)})
        for item in small
    ]
    repository.candidates = [*small, *spicy]
    result = service.compose_daily_meals(
        catalog_version=None,
        target=target("1800"),
        preferences=PreferenceReview(confirmed=True, taste_preferences=("香辣",)),
    )
    assert {meal.recipe_id for meal in result.meals} == {item.id for item in spicy}
    assert all(
        meal.matched_preference_summaries == ("偏好：香辣",) for meal in result.meals
    )


def test_lighter_replacement_uses_actual_fixed_meals_without_requiring_other_catalog_slots():
    service, repository, small, large = setup_pool()
    original = service.compose_daily_meals(
        catalog_version=None,
        target=target("2400"),
        preferences=PreferenceReview(confirmed=True),
    ).meals
    # Only lunch is still on sale. Breakfast and dinner are already saved snapshots.
    repository.candidates = [small[1], large[1]]
    result = ServiceTools(service).replace_planning_slot(
        user_id=uuid.uuid4(),
        target=target("2200"),
        preferences=PreferenceReview(confirmed=True),
        existing_meals=original,
        affected_slot=MealSlot.LUNCH,
        feedback_intent="lighter",
        replan_count=0,
    )
    assert result.action is PlanValidationAction.PASS
    assert result.meals[0] == original[0]
    assert result.meals[2] == original[2]
    assert result.meals[1].recipe_id == small[1].id
    assert result.meals[1].flavour_tags == ("清淡",)
    assert (
        service.validate_plan(target=target("2200"), meals=result.meals).action
        is PlanValidationAction.PASS
    )


def test_lighter_request_never_silently_substitutes_a_spicy_recipe():
    service, repository, _, large = setup_pool()
    original = service.compose_daily_meals(
        catalog_version=None,
        target=target("2400"),
        preferences=PreferenceReview(confirmed=True),
    ).meals
    repository.candidates = [large[1].model_copy(update={"id": uuid.uuid4()})]
    result = ServiceTools(service).replace_planning_slot(
        user_id=uuid.uuid4(),
        target=target("2400"),
        preferences=PreferenceReview(confirmed=True),
        existing_meals=original,
        affected_slot=MealSlot.LUNCH,
        feedback_intent="lighter",
        replan_count=0,
    )
    assert result.action is not PlanValidationAction.PASS
    assert result.meals == ()
    assert "清淡" in result.safe_message


@pytest.mark.parametrize("exclusion", ["花生", "不吃花生", "ＰＥＡＮＵＴ", " peanut "])
def test_exclusion_uses_controlled_aliases_even_when_dish_name_hides_the_ingredient(
    exclusion,
):
    item = food("Peanuts, roasted", aliases=("peanut", "花生"))
    bad = candidate(MealSlot.LUNCH, item, name="家常拌菜")
    service = PlanningService(
        repository=FakePlanningRepository(candidates=[bad]),
        nutrition_port=RecipeNutritionPort([item]),
    )
    prefs = PreferenceReview(confirmed=True, exclusions=(exclusion,))
    assert (
        service.keep_replaceable_food_identities(
            identities=((item.id, item.catalog_version),),
            affected_slot=MealSlot.LUNCH,
            exclude_recipe_ids=(),
            preferences=prefs,
        )
        == ()
    )
    assert (
        service.list_replacement_recipes(
            food_id=item.id,
            catalog_version=item.catalog_version,
            affected_slot=MealSlot.LUNCH,
            exclude_recipe_ids=(),
            preferences=prefs,
        )
        == ()
    )


def test_controlled_recipe_checks_ingredient_alias_not_just_recipe_name():
    item = food("Peanuts, roasted", aliases=("花生",))
    recipe = controlled_recipe(slot=MealSlot.LUNCH, food=item, name="家常拌菜")
    service = PlanningService(
        repository=FakePlanningRepository([recipe]),
        nutrition_port=RecipeNutritionPort([item]),
    )
    result = service.compose_daily_meals(
        catalog_version=item.catalog_version,
        preferences=PreferenceReview(confirmed=True, exclusions=("花生",)),
    )
    assert result.action is not PlanValidationAction.PASS
    assert result.meals == ()


def test_target_relaxation_cannot_mask_an_independent_macro_ratio_failure():
    service, _, _, _ = setup_pool()
    meals = tuple(
        meal.model_copy(
            update={
                "nutrients": meal.nutrients.model_copy(
                    update={"energy_kcal": Decimal("700"), "fat_g": Decimal("1")}
                )
            }
        )
        for meal in valid_daily_meals()
    )
    result = service.validate_plan(
        target=validation_target(), meals=meals, allow_target_relaxation=True
    )
    assert result.action is PlanValidationAction.REPLAN
    assert result.rule_id == "fat_g-ratio-out-of-range"


def test_candidate_limit_stops_before_unbounded_nutrition_queries():
    service, repository, small, _ = setup_pool()
    repository.candidates = [small[0]] * (MAX_RECIPE_CANDIDATES + 1)
    result = service.compose_daily_meals(
        catalog_version=None, preferences=PreferenceReview(confirmed=True)
    )
    assert result.action is PlanValidationAction.NEEDS_INPUT
    assert result.meals == ()


def test_first_use_can_compose_active_controlled_recipes_without_a_pinned_catalog():
    items = [food(slot.value) for slot in REQUIRED_MEAL_SLOTS]
    recipes = [
        controlled_recipe(slot=slot, food=item, name=slot.value)
        for slot, item in zip(REQUIRED_MEAL_SLOTS, items, strict=True)
    ]
    repository = FakePlanningRepository(recipes)
    service = PlanningService(
        repository=repository, nutrition_port=RecipeNutritionPort(items)
    )
    result = service.compose_daily_meals(
        catalog_version=None,
        target=target("1800"),
        preferences=PreferenceReview(confirmed=True),
    )
    assert result.action is PlanValidationAction.PASS
    assert len(result.meals) == 3


def test_an_administratively_empty_pool_never_reactivates_bootstrap_recipes():
    class ManagedPoolRepository(FakePlanningRepository):
        def has_managed_recipe_candidates(self):
            return True

    repository = ManagedPoolRepository()
    service = PlanningService(
        repository=repository, nutrition_port=RecipeNutritionPort([])
    )
    result = service.compose_daily_meals(
        catalog_version=None,
        target=target("1800"),
        preferences=PreferenceReview(confirmed=True),
    )
    assert result.action is PlanValidationAction.REPLAN
    assert repository.recipe_search_calls == 0
