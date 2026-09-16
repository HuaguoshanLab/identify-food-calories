"""Component portions retain source evidence and bounded, authoritative calculations."""

from collections import Counter
from decimal import Decimal
from uuid import uuid4

import pytest

from app.nutrition.schemas import NutritionAction, NutritionCalculationResult
from app.planning.bundles import BundlePool
from app.planning.diagnostics import SearchDiagnostics, SlotDiagnostics, ScanStop
from app.agent.graph import _planning_report
from app.planning.archive_schemas import PlanArchiveWrite, PlanComponentRecipeEvidence, PlanReport
from app.planning.archive_service import PlanArchiveService
from app.planning.schemas import DailyTarget, MealSlot, PlanValidationAction, PreferenceReview
from app.planning.selection import MealSelectionPolicy, PlanningSearchBudget, select_meals
from app.planning.service import PlanningService
from tests.planning.test_meal_bundles import fixtures, compose, service_for
from tests.planning.test_planning_service import FakePlanningRepository
from tests.planning.test_portion_adaptation import RecordingNutrition
from tests.planning.test_plan_archive import FakeArchive, NOW, OWNER


def component_pool(*, alternatives=1, energy=Decimal(400), clock=lambda: 0, **policy):
    foods, rows, _ = fixtures(alternatives=alternatives)
    port = RecordingNutrition(foods)
    settings = MealSelectionPolicy(**policy)
    service = PlanningService(repository=FakePlanningRepository(candidates=rows), nutrition_port=port, selection_policy=settings)
    stats = SlotDiagnostics()
    prefs = PreferenceReview(confirmed=True)
    pool = BundlePool(slot=MealSlot.LUNCH, energy=energy, policy=settings, preferences=prefs, recent=(), stats=stats, clock=clock)
    for row in rows:
        if row.meal_slot is MealSlot.LUNCH:
            pool.add(row, service._build_managed_meal(row, prefs, allow_component=True))

    def adapt(row, meal, desired):
        grams = service._portion_for_energy(meal, desired)
        return meal if grams is None else service._build_managed_meal(row, prefs, allow_component=True, portion_grams=grams)

    return pool, adapt, port, rows, service


def test_each_role_has_its_own_bounded_portion_and_catalog_calculation():
    pool, adapt, port, rows, _ = component_pool()
    before = [row.model_dump() for row in rows]
    original, adjusted = [option.meal for option in pool.finish(excluded=(), adapt=adapt)]
    assert [item.portion_grams for item in original.items] == [200, 100, 150]
    assert [item.portion_grams for item in adjusted.items] == [150, 78, 187]
    assert [item.nutrients.energy_kcal for item in adjusted.items] == [Decimal(225), Decimal('140.4'), Decimal('74.8')]
    assert adjusted.nutrients.energy_kcal == Decimal('440.2')
    assert adjusted.portion_grams == 415
    for item in adjusted.items:
        assert any(r.food_id == item.nutrition_item_id and r.catalog_version == item.catalog_version and r.grams == item.portion_grams for r in port.requests)
        assert '按目标调整份量' in item.portion_description
        assert item.recipe_revision == 1
    assert adjusted.recipe_id == original.recipe_id
    assert adjusted.source_recipe_ids == original.source_recipe_ids
    assert [row.model_dump() for row in rows] == before
    assert len(port.requests) == 6


@pytest.mark.parametrize('case', ['disabled', 'no_target', 'count_limit', 'excluded', 'missing_role'])
def test_no_extra_calculations_without_an_eligible_adaptation(case):
    kwargs = {'portion_adjustment_enabled': False} if case == 'disabled' else {}
    if case == 'count_limit':
        kwargs['bundle_max_combinations'] = 1
    pool, adapt, port, _, _ = component_pool(energy=None if case == 'no_target' else Decimal(400), **kwargs)
    base = next(pool.finish(excluded=())).meal
    if case == 'missing_role':
        pool.pools['vegetable'].clear()
    port.requests.clear()
    result = list(pool.finish(excluded=(base.recipe_id,) if case == 'excluded' else (), adapt=adapt))
    assert len(result) == (0 if case in {'excluded', 'missing_role'} else 1)
    assert not port.requests
    if case == 'count_limit':
        assert pool.stats.bundle_stop is ScanStop.COUNT


def test_only_retained_components_are_recalculated_once_and_variants_share_budget():
    pool, adapt, port, _, _ = component_pool(alternatives=10, bundle_options_per_role=2, bundle_max_combinations=9)
    port.requests.clear()
    results = list(pool.finish(excluded=(), adapt=adapt))
    assert len(results) == 9
    assert pool.stats.bundle_attempts == 9
    assert pool.stats.bundle_stop is ScanStop.COUNT
    assert 0 < len(port.requests) <= 6
    assert max(Counter(r.food_id for r in port.requests).values()) == 1
    assert pool.stats.adapted_components == len(port.requests)


def test_slow_recalculation_stops_further_work_and_keeps_original_bundle():
    now = [0.0]
    pool, adapt, port, _, _ = component_pool(clock=lambda: now[0])
    port.requests.clear()

    def slow(row, meal, desired):
        value = adapt(row, meal, desired)
        now[0] = 1
        return value

    results = list(pool.finish(excluded=(), adapt=slow))
    assert len(results) == 1
    assert len(port.requests) == 1
    assert pool.stats.bundle_stop is ScanStop.TIME
    assert pool.stats.adapted_bundles == 0


def test_failed_calculation_cannot_supply_scaled_nutrients_and_original_survives():
    pool, adapt, port, _, _ = component_pool()
    port.calculate_nutrition = lambda request: NutritionCalculationResult(action=NutritionAction.BLOCK, safe_message='不可计算')
    results = list(pool.finish(excluded=(), adapt=adapt))
    assert len(results) == 1
    assert [item.portion_grams for item in results[0].meal.items] == [200, 100, 150]


def test_equal_total_grams_do_not_collapse_different_component_portions():
    pool, _, _, _, service = component_pool()
    grams = {'staple': Decimal(190), 'protein': Decimal(110), 'vegetable': Decimal(150)}

    def redistribute(row, meal, desired):
        return service._build_managed_meal(row, PreferenceReview(confirmed=True), allow_component=True, portion_grams=grams[row.meal_role])

    options = list(pool.finish(excluded=(), adapt=redistribute))
    assert options[0].meal.portion_grams == options[1].meal.portion_grams == 450
    assert options[0].identity != options[1].identity
    _, _, target = fixtures()
    # Reuse this pool's catalog/IDs for fixed meals, so only portion distribution differs.
    base = compose(service, target).meals
    fixed = (base[0], base[2])
    selected = []
    for order in (options, list(reversed(options))):
        diagnostics = SearchDiagnostics()
        selected.append(select_meals(options=order, target=None, preferences=PreferenceReview(confirmed=True),
                                     recent_recipe_ids=(), fixed_meals=fixed, validation_rank=lambda meals: 0,
                                     budget=PlanningSearchBudget(options_per_slot=2), policy=MealSelectionPolicy(diversity_slots=0),
                                     clock=lambda: 0, diagnostics=diagnostics))
        assert diagnostics.slots[MealSlot.LUNCH].shortlisted == 2
    assert selected[0] == selected[1]


def test_replacement_uses_residual_including_snack_and_never_recalculates_fixed_components():
    foods, rows, target = fixtures(alternatives=2)
    initial = compose(service_for(foods, rows), target).meals
    snack = initial[0].model_copy(update={'recipe_id': uuid4(), 'slot': MealSlot.SNACK,
                                        'nutrients': initial[0].nutrients.model_copy(update={'energy_kcal': Decimal(100)})})
    fixed = (initial[0], initial[2], snack)
    port = RecordingNutrition(foods)
    service = PlanningService(repository=FakePlanningRepository(candidates=rows), nutrition_port=port)
    result = compose(service, target, fixed_meals=fixed, required_slot=MealSlot.LUNCH,
                     exclude_recipe_ids=(initial[1].recipe_id,))
    assert result.meals[0] is fixed[0] and result.meals[2] is fixed[1] and result.meals[3] is fixed[2]
    assert result.meals[1].recipe_id != initial[1].recipe_id
    assert service._slot_energy(target, fixed, MealSlot.LUNCH) == 440
    assert all(request.food_id != foods[0].id for request in port.requests)
    assert all(request.grams in {Decimal(200), Decimal(100), Decimal(150), Decimal(86), Decimal(187)} for request in port.requests)


def test_adjusted_bundles_meet_a_target_original_portions_cannot_and_archive_actual_amounts():
    foods, rows, original_target = fixtures()
    initial = compose(service_for(foods, rows), original_target).meals
    target = DailyTarget.model_validate({
        'energy_kcal': {'lower': 1200, 'upper': 1300},
        'protein_g': {'lower': 50, 'upper': 120},
        'fat_g': {'lower': 20, 'upper': 70},
        'carbohydrate_g': {'lower': 130, 'upper': 220},
    })
    service = PlanningService(repository=FakePlanningRepository(candidates=rows), nutrition_port=RecordingNutrition(foods),
                              selection_policy=MealSelectionPolicy(max_target_deviation=0))
    assert service.validate_plan(target=target, meals=initial).action is PlanValidationAction.REPLAN
    meals = compose(service, target, fixed_meals=(initial[0],), required_slot=MealSlot.LUNCH).meals
    assert meals[0] is initial[0]
    assert service.validate_plan(target=target, meals=meals).action is PlanValidationAction.PASS
    assert [item.portion_grams for item in meals[1].items] == [150, 88, 187]
    assert [item.portion_grams for item in meals[2].items] == [150, 77, 187]
    report = PlanReport.model_validate(_planning_report(target=target, meals=meals))
    evidence = tuple(PlanComponentRecipeEvidence(recipe_id=item.recipe_id, recipe_version=f'managed-candidate.v{item.recipe_revision}',
                                                catalog_version=item.catalog_version, audit_version=f'candidate-revision.v{item.recipe_revision}')
                     for meal in meals for item in meal.items)
    repo = FakeArchive()
    archive = PlanArchiveService(repository=repo, now=lambda: NOW)
    archive.record_completion(PlanArchiveWrite(user_id=OWNER, run_id=uuid4(), thread_id=uuid4(), started_at=NOW,
        report=report, recipe_ids=tuple(identity for meal in meals for identity in meal.source_recipe_ids),
        component_recipes=evidence, target_version='target.v1', formula_version='formula.v1', graph_version='graph.v1', tool_version='tool.v1'))
    saved = archive.detail(OWNER, repo.plans[0].id).report
    assert saved.meals[1].items == report.meals[1].items
    assert saved.meals[2].items == report.meals[2].items
    assert '原份量 200g' in saved.meals[1].items[0].portion_description
