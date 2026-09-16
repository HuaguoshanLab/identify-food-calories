"""Meal distribution and diversity are bounded soft choices, not nutrition authority."""

from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.planning.diagnostics import SearchDiagnostics
from app.planning.schemas import MealSlot, PreferenceReview
from app.planning.selection import MealSelectionPolicy, PlanningSearchBudget, SelectionCandidate, _Shortlist, select_meals
from tests.planning.test_personalized_selection import target
from tests.planning.test_planning_service import valid_daily_meals


def candidate(slot, energy, identity, *, food_id=1, method="蒸"):
    base = valid_daily_meals()[0]
    energy = Decimal(energy)
    meal = base.model_copy(update={
        "slot": slot, "recipe_id": UUID(int=identity), "display_name": f"不同菜名{identity}",
        "method_tags": (method,), "flavour_tags": ("清淡",),
        "nutrients": base.nutrients.model_copy(update={
            "energy_kcal": energy, "protein_g": energy * Decimal("0.20") / 4,
            "carbohydrate_g": energy * Decimal("0.50") / 4,
            "fat_g": energy * Decimal("0.30") / 9,
        }),
    })
    return SelectionCandidate(meal, frozenset((UUID(int=food_id),)))


def choose(options, *, policy=None, fixed=(), count=12, validation_rank=lambda meals: 0, daily_target=None, diagnostics=None):
    return select_meals(options=iter(options), target=daily_target or target("1800"),
                        preferences=PreferenceReview(confirmed=True), recent_recipe_ids=(),
                        fixed_meals=fixed, validation_rank=validation_rank, policy=policy,
                        budget=PlanningSearchBudget(options_per_slot=count), diagnostics=diagnostics)


def test_configured_distribution_changes_shortlisting_instead_of_forcing_equal_meals():
    options = [candidate(slot, energy, index + 1) for index, (slot, energy) in enumerate([
        (MealSlot.BREAKFAST, "450"), (MealSlot.BREAKFAST, "600"),
        (MealSlot.LUNCH, "720"), (MealSlot.LUNCH, "600"),
        (MealSlot.DINNER, "630"), (MealSlot.DINNER, "600"),
    ])]
    selected = choose(options, count=1)
    assert [meal.nutrients.energy_kcal for meal in selected] == [450, 720, 630]
    equal = choose(options, count=1, policy=MealSelectionPolicy(breakfast_weight=1, lunch_weight=1, dinner_weight=1))
    assert [meal.nutrients.energy_kcal for meal in equal] == [600, 600, 600]
    assert all(any(meal is option.meal for option in options) for meal in selected)


def test_replacement_uses_residual_including_fixed_snack_and_preserves_other_meals():
    fixed = (candidate(MealSlot.BREAKFAST, "450", 1).meal,
             candidate(MealSlot.DINNER, "630", 2).meal,
             candidate(MealSlot.SNACK, "100", 3).meal)
    selected = choose([candidate(MealSlot.LUNCH, "620", 4), candidate(MealSlot.LUNCH, "720", 5)], fixed=fixed, count=1)
    assert [meal.nutrients.energy_kcal for meal in selected] == [450, 620, 630, 100]
    assert all(any(meal is original for meal in selected) for original in fixed)


def test_partial_replanning_renormalizes_weights_over_only_remaining_slots():
    # After a 600 kcal breakfast, lunch/dinner split 1200 at 40:35, not 40%/35% of 1800.
    fixed = (candidate(MealSlot.BREAKFAST, "600", 1).meal,)
    selected = choose([
        candidate(MealSlot.LUNCH, "640", 2), candidate(MealSlot.LUNCH, "720", 3),
        candidate(MealSlot.DINNER, "560", 4), candidate(MealSlot.DINNER, "630", 5),
    ], fixed=fixed, count=1)
    assert [meal.nutrients.energy_kcal for meal in selected] == [600, 640, 560]


def varied_pool():
    return [candidate(MealSlot.BREAKFAST, "450", 1), candidate(MealSlot.DINNER, "630", 2),
            *(candidate(MealSlot.LUNCH, "720", index) for index in range(3, 30)),
            candidate(MealSlot.LUNCH, "725", 100, food_id=2, method="炖")]


def tolerant_target():
    daily_target = target("1800")
    return daily_target.model_copy(update={"energy_kcal": daily_target.energy_kcal.model_copy(update={"lower": Decimal("1750"), "upper": Decimal("1850")})})


def test_diversity_reservation_keeps_a_different_composition_after_many_renamed_duplicates():
    options = varied_pool()
    selected = choose(options, count=3, daily_target=tolerant_target())
    assert selected[1].recipe_id == UUID(int=100)
    disabled = choose(options, count=3, daily_target=tolerant_target(), policy=MealSelectionPolicy(diversity_slots=0, diversity_weight=0))
    assert disabled[1].recipe_id != UUID(int=100)
    assert choose(list(reversed(options)), count=3, daily_target=tolerant_target()) == selected
    assert "food_ids" not in selected[1].model_dump()


def test_different_methods_can_diversify_when_ingredient_structure_is_unavailable():
    options = [SelectionCandidate(item.meal) for item in varied_pool()]
    selected = choose(options, count=3, daily_target=tolerant_target(), policy=MealSelectionPolicy(diversity_weight=1))
    assert selected[1].method_tags == ("炖",)


def test_nutrition_validation_beats_diversity_and_repetition_never_becomes_a_hard_rejection():
    selected = choose(varied_pool(), count=3, daily_target=tolerant_target(),
                      policy=MealSelectionPolicy(diversity_weight=1),
                      validation_rank=lambda meals: 2 if meals[1].recipe_id == UUID(int=100) else 0)
    assert selected[1].recipe_id != UUID(int=100)
    assert len(selected) == 3
    only = [candidate(slot, energy, index + 1) for index, (slot, energy) in enumerate([
        (MealSlot.BREAKFAST, "450"), (MealSlot.LUNCH, "720"), (MealSlot.DINNER, "630")])]
    assert len(choose(only)) == 3


def test_diversity_buffer_and_combination_count_remain_bounded():
    pool = _Shortlist(12, 4)
    for identity in range(1, 300):
        option = candidate(MealSlot.LUNCH, "720", identity, food_id=identity)
        pool.add(option, (identity,))
        assert len(pool.primary) <= 12 and len(pool.groups) <= 12
    assert len(pool.finish()) == 12
    diagnostics = SearchDiagnostics()
    choose(varied_pool(), count=3, daily_target=tolerant_target(), diagnostics=diagnostics)
    assert diagnostics.combinations <= 27
    assert all(slot.shortlisted <= 3 for slot in diagnostics.slots.values())


@pytest.mark.parametrize(("field", "value"), [
    ("breakfast_weight", 0), ("lunch_weight", -1), ("dinner_weight", "NaN"),
    ("dinner_weight", "Infinity"), ("diversity_slots", -1), ("diversity_slots", 65),
    ("diversity_weight", -1), ("diversity_weight", "NaN"), ("diversity_weight", 2),
])
def test_invalid_selection_config_fails_closed(field, value):
    with pytest.raises(ValidationError):
        MealSelectionPolicy(**{field: value})
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{f"planning_{field}": value})


@pytest.mark.parametrize("managed", [True, False])
def test_domain_service_passes_catalog_evidence_and_still_applies_exclusions(managed):
    from app.planning.service import PlanningService
    from app.planning.schemas import PlanValidationAction
    from tests.planning.test_personalized_selection import food
    from tests.planning.test_planning_service import FakePlanningRepository, RecipeNutritionPort, controlled_recipe, managed_candidate

    shared, alternative = food("已知搭配"), food("另一搭配", aliases=("花生",))
    rows = []
    for option in varied_pool():
        item = alternative if option.meal.recipe_id.int == 100 else shared
        grams = option.meal.nutrients.energy_kcal / 6
        row = managed_candidate(slot=option.meal.slot, food=item) if managed else controlled_recipe(slot=option.meal.slot, food=item, name=option.meal.display_name)
        update = {"id": option.meal.recipe_id, "display_name": option.meal.display_name, "portion_grams": grams,
                  "method_tags": option.meal.method_tags, "flavour_tags": ("清淡",)}
        if not managed:
            update["ingredients"] = (row.ingredients[0].model_copy(update={"grams": grams}),)
        rows.append(row.model_copy(update=update))
    repository = FakePlanningRepository(candidates=rows) if managed else FakePlanningRepository(recipes=rows)
    service = PlanningService(repository=repository, nutrition_port=RecipeNutritionPort([shared, alternative]),
                              search_budget=PlanningSearchBudget(options_per_slot=3, batch_size=2))
    result = service.compose_daily_meals(catalog_version=None, target=tolerant_target(), preferences=PreferenceReview(confirmed=True))
    assert result.meals[1].recipe_id == UUID(int=100)
    assert service.validate_plan(target=tolerant_target(), meals=result.meals).action is PlanValidationAction.PASS
    excluded = service.compose_daily_meals(catalog_version=None, target=tolerant_target(), preferences=PreferenceReview(confirmed=True, exclusions=("花生",)))
    assert excluded.meals[1].recipe_id != UUID(int=100)
    assert service.validate_plan(target=tolerant_target(), meals=excluded.meals).action is PlanValidationAction.PASS
