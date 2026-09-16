"""Taste variety uses known labels, stays optional and never overrides preferences or validation."""

from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.planning.diagnostics import SearchDiagnostics
from app.planning.schemas import MealSlot, PlanValidationAction, PreferenceReview
from app.planning.selection import MealSelectionPolicy, PlanningSearchBudget, SelectionCandidate, _Shortlist, _similarity, select_meals
from app.planning.service import PlanningService
from tests.planning.test_meal_distribution import candidate
from tests.planning.test_personalized_selection import food, target
from tests.planning.test_planning_service import FakePlanningRepository, RecipeNutritionPort, managed_candidate


def option(slot, energy, identity, flavours):
    base = candidate(slot, energy, identity)
    return SelectionCandidate(base.meal.model_copy(update={"flavour_tags": flavours}), base.food_ids)


def pool(base=("咸鲜",), alternative=("酸甜",)):
    return [option(MealSlot.BREAKFAST, "450", 1, base),
            option(MealSlot.LUNCH, "720", 2, base),
            option(MealSlot.DINNER, "630", 3, base),
            option(MealSlot.LUNCH, "720", 100, alternative)]


def choose(options, *, preferences=(), policy=None, fixed=(), count=12, rank=lambda meals: 0, diagnostics=None):
    return select_meals(options=iter(options), target=target("1800"),
                        preferences=PreferenceReview(confirmed=True, taste_preferences=preferences),
                        recent_recipe_ids=(), fixed_meals=fixed, validation_rank=rank,
                        policy=policy, budget=PlanningSearchBudget(options_per_slot=count), diagnostics=diagnostics)


def test_same_nutrition_ingredients_and_methods_can_still_offer_another_flavour():
    options = pool()
    selected = choose(options)
    assert selected[1].flavour_tags == ("酸甜",)
    assert choose(list(reversed(options))) == selected
    disabled = choose(options, policy=MealSelectionPolicy(flavour_diversity_weight=0))
    assert disabled[1].flavour_tags == ("咸鲜",)
    assert [meal.nutrients for meal in selected] == [meal.nutrients for meal in disabled]


def test_flavour_representative_survives_many_same_composition_candidates_within_budget():
    options = pool()
    options[1:1] = [option(MealSlot.LUNCH, "720", identity, ("咸鲜",)) for identity in range(4, 90)]
    diagnostics = SearchDiagnostics()
    selected = choose(options, count=2, diagnostics=diagnostics)
    assert selected[1].flavour_tags == ("酸甜",)
    assert diagnostics.combinations <= 8
    assert diagnostics.slots[MealSlot.LUNCH].shortlisted == 2
    shortlist = _Shortlist(2, 1, flavour_weight=Decimal("0.25"))
    for index in range(100):
        item = option(MealSlot.LUNCH, "720", index + 1, (f"已标注口味{index}",))
        shortlist.add(item, (index,))
        assert len(shortlist.primary) <= 2 and len(shortlist.groups) <= 2


def test_explicit_favourite_wins_even_at_maximum_flavour_diversity_weight():
    selected = choose(pool(), preferences=("咸鲜",), count=2,
                      policy=MealSelectionPolicy(flavour_diversity_weight=1, diversity_weight=1))
    assert all(meal.flavour_tags == ("咸鲜",) for meal in selected)


def test_preferred_flavour_is_exempt_but_other_flavours_can_still_vary():
    selected = choose(pool(("清淡", "咸鲜"), ("清淡", "酸甜")), preferences=("清淡",))
    assert selected[1].flavour_tags == ("清淡", "酸甜")
    assert all("清淡" in meal.flavour_tags for meal in selected)
    a, b = pool(("清淡",), ("清淡",))[:2]
    assert _similarity(a, b, flavour_weight=Decimal(1), preferred_flavours=frozenset(("清淡",))) == _similarity(a, b)


def test_reserved_candidates_do_not_trade_a_favourite_for_novelty():
    shortlist = _Shortlist(2, 1, flavour_weight=Decimal(1), preferred_flavours=frozenset(("清淡",)))
    for index, flavours in enumerate([("清淡",), ("清淡",), ("香辣",)]):
        shortlist.add(option(MealSlot.LUNCH, "720", index + 1, flavours), (index,))
    assert all(item.meal.flavour_tags == ("清淡",) for item in shortlist.finish())


@pytest.mark.parametrize("tags", [(), (" ",), (" 咸 鲜 ", "咸鲜", "咸鲜")])
def test_missing_or_duplicate_labels_cannot_claim_a_new_flavour(tags):
    options = pool(alternative=tags)
    # Give the unknown/same-flavour candidate the first tie-break ID.
    options[-1] = SelectionCandidate(options[-1].meal.model_copy(update={"recipe_id": UUID(int=0)}), options[-1].food_ids)
    options.append(option(MealSlot.LUNCH, "720", 101, ("酸甜",)))
    assert choose(options)[1].flavour_tags == ("酸甜",)


def test_single_replacement_uses_saved_flavours_and_does_not_change_fixed_cards():
    options = pool()
    fixed = (options[0].meal, options[2].meal)
    selected = choose([options[1], options[3]], fixed=fixed)
    assert selected[0] is fixed[0] and selected[2] is fixed[1]
    assert selected[1].flavour_tags == ("酸甜",)


def test_nutrition_rank_wins_and_repeated_flavour_is_valid_when_no_alternative_exists():
    selected = choose(pool(), rank=lambda meals: 2 if meals[1].flavour_tags == ("酸甜",) else 0)
    assert selected[1].flavour_tags == ("咸鲜",)
    assert len(choose(pool()[:3])) == 3


def test_domain_service_excludes_spicy_variant_before_flavour_selection():
    item = food("测试基准")
    rows = [managed_candidate(slot=entry.meal.slot, food=item).model_copy(update={
        "id": entry.meal.recipe_id, "portion_grams": entry.meal.nutrients.energy_kcal / 6,
        "flavour_tags": entry.meal.flavour_tags, "method_tags": ("蒸",),
    }) for entry in pool(alternative=("香辣",))]
    service = PlanningService(repository=FakePlanningRepository(candidates=rows), nutrition_port=RecipeNutritionPort([item]))
    unconstrained = service.compose_daily_meals(catalog_version=None, target=target("1800"),
                                                preferences=PreferenceReview(confirmed=True))
    assert unconstrained.meals[1].flavour_tags == ("香辣",)
    result = service.compose_daily_meals(catalog_version=None, target=target("1800"),
                                        preferences=PreferenceReview(confirmed=True, exclusions=("不吃辣",)))
    assert len(result.meals) == 3
    assert all("香辣" not in meal.flavour_tags for meal in result.meals)
    assert service.validate_plan(target=target("1800"), meals=result.meals).action is PlanValidationAction.PASS


@pytest.mark.parametrize("value", [-1, 2, "NaN", "Infinity"])
def test_invalid_flavour_weight_fails_closed(value):
    with pytest.raises(ValidationError):
        MealSelectionPolicy(flavour_diversity_weight=value)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, planning_flavour_diversity_weight=value)
