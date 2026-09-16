"""Calculated meal components stay bounded, traceable and immutable on replacement."""
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.agent.graph import _planning_report
from app.planning.archive_schemas import PlanReport, PlanArchiveWrite, PlanComponentRecipeEvidence
from app.planning.archive_service import PlanArchiveService
from app.planning.bundles import BundlePool
from app.planning.diagnostics import SlotDiagnostics, ScanStop
from app.planning.schemas import DailyTarget, MealSlot, PlannedMeal, PlanValidationAction, PreferenceReview
from app.planning.selection import MealSelectionPolicy, PlanningSearchBudget
from app.planning.service import PlanningService
from app.nutrition.schemas import NutritionValues
from tests.planning.test_planning_service import FakePlanningRepository, RecipeNutritionPort, managed_candidate, qualified_food
from tests.planning.test_plan_archive import FakeArchive, NOW, OWNER


def fixtures(*, alternatives=1):
    foods, rows = [], []
    for name, role, grams, nutrients in (
        ('早餐', 'standalone', '100', ('400', '20', '10', '60')),
        ('米饭', 'staple', '200', ('150', '3', '1', '32')),
        ('鸡胸肉', 'protein', '100', ('180', '25', '8', '2')),
        ('青菜', 'vegetable', '150', ('40', '2', '1', '6')),
    ):
        for index in range(alternatives if role != 'standalone' else 1):
            food = qualified_food(name=f'{name}{index}', energy=nutrients[0]).model_copy(update={
                'nutrients_per_100g': NutritionValues(**dict(zip(('energy_kcal', 'protein_g', 'fat_g', 'carbohydrate_g'), map(Decimal, nutrients), strict=True)))
            })
            foods.append(food)
            for slot in ([MealSlot.BREAKFAST] if role == 'standalone' else [MealSlot.LUNCH, MealSlot.DINNER]):
                rows.append(managed_candidate(slot=slot, food=food).model_copy(update={
                    'meal_role': role, 'portion_grams': Decimal(grams), 'flavour_tags': ('清淡',),
                }))
    target = DailyTarget.model_validate({
        'energy_kcal': {'lower': '1460', 'upper': '1500'},
        'protein_g': {'lower': '70', 'upper': '100'},
        'fat_g': {'lower': '30', 'upper': '45'},
        'carbohydrate_g': {'lower': '200', 'upper': '230'},
    })
    return foods, rows, target


def service_for(foods, rows, **policy):
    return PlanningService(repository=FakePlanningRepository(candidates=rows), nutrition_port=RecipeNutritionPort(foods),
                           selection_policy=MealSelectionPolicy(portion_adjustment_enabled=False, **policy))


def compose(service, target, **kwargs):
    return service.compose_daily_meals(catalog_version=None, target=target, preferences=PreferenceReview(confirmed=True), **kwargs)


def test_composes_complete_roles_calculates_totals_and_emits_no_internal_identities():
    foods, rows, target = fixtures()
    service = service_for(foods, rows)
    result = compose(service, target)
    assert result.action is PlanValidationAction.PASS
    breakfast, lunch, dinner = result.meals
    assert not breakfast.items
    assert tuple(item.meal_role for item in lunch.items) == ('staple', 'protein', 'vegetable')
    assert lunch.nutrients.energy_kcal == dinner.nutrients.energy_kcal == Decimal('540')
    assert lunch.portion_grams == Decimal('450')
    assert lunch.nutrients.protein_g == Decimal('34')
    assert len(lunch.source_recipe_ids) == 3 and lunch.recipe_id not in lunch.source_recipe_ids
    assert service.validate_plan(target=target, meals=result.meals).action is PlanValidationAction.PASS
    report = _planning_report(target=target, meals=result.meals)
    public = PlanReport.model_validate(report)
    assert len(public.meals[1].items) == 3
    assert public.meals[1].items[0].portion_grams == '200'
    assert 'recipe_id' not in str(report) and 'catalog_version' not in str(report)
    # Iteration order cannot change a complete bounded search.
    assert compose(service_for(foods, list(reversed(rows))), target).meals == result.meals


@pytest.mark.parametrize('case', ['missing_role', 'excluded', 'unavailable', 'disabled', 'same_food'])
def test_incomplete_or_unsafe_bundles_never_escape_as_whole_meals(case):
    foods, rows, target = fixtures()
    prefs = PreferenceReview(confirmed=True)
    policy = {}
    if case == 'missing_role':
        rows = [row for row in rows if row.meal_role != 'vegetable']
    if case == 'excluded':
        prefs = PreferenceReview(confirmed=True, exclusions=('青菜',))
    if case == 'unavailable':
        foods = [food for food in foods if not food.canonical_name.startswith('青菜')]
    if case == 'disabled':
        policy['bundle_enabled'] = False
    if case == 'same_food':
        same = next(row.nutrition_item_id for row in rows if row.meal_role == 'protein')
        rows = [row.model_copy(update={'nutrition_item_id': same}) if row.meal_role == 'vegetable' else row for row in rows]
    service = service_for(foods, rows, **policy)
    result = service.compose_daily_meals(catalog_version=None, target=target, preferences=prefs)
    assert result.action is PlanValidationAction.REPLAN and not result.meals


def test_replacing_a_bundle_preserves_fixed_component_snapshots_and_rejects_the_current_bundle():
    foods, rows, target = fixtures(alternatives=2)
    service = service_for(foods, rows)
    original = compose(service, target).meals
    result = compose(service, target, fixed_meals=(original[0], original[2]), required_slot=MealSlot.LUNCH,
                     feedback_intent='lighter', exclude_recipe_ids=(original[1].recipe_id,))
    assert result.action is PlanValidationAction.PASS
    assert result.meals[0] == original[0] and result.meals[2] == original[2]
    assert result.meals[1].recipe_id != original[1].recipe_id
    assert len(result.meals[1].items) == 3
    # A single unknown/spicy component must not inherit "清淡" from its companions.
    rows = [row.model_copy(update={'flavour_tags': ('麻辣',)}) if row.meal_role == 'protein' else row for row in rows]
    failure = compose(service_for(foods, rows), target, fixed_meals=(original[0], original[2]), required_slot=MealSlot.LUNCH, feedback_intent='lighter')
    assert failure.action is PlanValidationAction.REPLAN


def test_component_pool_and_work_budgets_bound_many_combinations():
    foods, rows, target = fixtures(alternatives=10)
    service = service_for(foods, rows)
    stats = SlotDiagnostics()
    pool = BundlePool(slot=MealSlot.LUNCH, energy=Decimal('540'), policy=MealSelectionPolicy(bundle_options_per_role=2, bundle_max_combinations=3), preferences=PreferenceReview(confirmed=True), recent=(), stats=stats, clock=lambda: 0)
    for row in rows:
        if row.meal_slot is MealSlot.LUNCH:
            meal = service._build_managed_meal(row, PreferenceReview(confirmed=True), allow_component=True)
            pool.add(row, meal)
    assert all(len(entries) == 2 for entries in pool.pools.values())
    assert len(tuple(pool.finish(excluded=()))) == 3
    assert stats.bundle_attempts == 3 and stats.bundle_stop is ScanStop.COUNT
    times = iter([0, 1])
    pool.clock = lambda: next(times)
    assert tuple(pool.finish(excluded=())) == ()
    assert stats.bundle_stop is ScanStop.TIME
    # SQL/scan budgets remain independently enforced before component assembly.
    repo = FakePlanningRepository(candidates=rows)
    service = PlanningService(repository=repo, nutrition_port=RecipeNutritionPort(foods), search_budget=PlanningSearchBudget(scan_per_slot=1))
    assert compose(service, target).action is PlanValidationAction.REPLAN


@pytest.mark.parametrize('field', ['nutrients', 'portion_grams', 'items'])
def test_runtime_validation_rejects_corrupted_bundle_totals_or_missing_roles(field):
    foods, rows, target = fixtures()
    meal = compose(service_for(foods, rows), target).meals[1]
    data = meal.model_dump()
    if field == 'nutrients':
        data[field]['energy_kcal'] = '1'
    elif field == 'portion_grams':
        data[field] = '1'
    else:
        data[field] = data[field][:2]
    with pytest.raises(ValidationError):
        PlannedMeal.model_validate(data)


def test_archive_freezes_every_component_and_uses_observed_versions_instead_of_live_roles():
    foods, rows, target = fixtures()
    meals = compose(service_for(foods, rows), target).meals
    evidence = tuple(PlanComponentRecipeEvidence(recipe_id=item.recipe_id, recipe_version=f'managed-candidate.v{item.recipe_revision}', catalog_version=item.catalog_version, audit_version=f'candidate-revision.v{item.recipe_revision}') for meal in meals for item in meal.items)
    payload = dict(user_id=OWNER, run_id=uuid4(), thread_id=uuid4(), started_at=NOW, report=PlanReport.model_validate(_planning_report(target=target, meals=meals)), recipe_ids=tuple(identity for meal in meals for identity in meal.source_recipe_ids), component_recipes=evidence, target_version='target.v1', formula_version='formula.v1', graph_version='graph.v1', tool_version='tool.v1')
    repo = FakeArchive()
    requested_ids = []
    def live_versions(ids):
        requested_ids.extend(ids)
        return [{'recipe_id': str(identity), 'recipe_version': 'live-v999'} for identity in ids]
    repo.recipe_versions = live_versions
    service = PlanArchiveService(repository=repo, now=lambda: NOW)
    service.record_completion(PlanArchiveWrite(**payload))
    assert requested_ids == [meals[0].recipe_id]
    version = repo.versions[0]
    assert version.provenance['schema_version'] == 'diet-plan-snapshot.v2'
    assert len(version.provenance['recipes']) == 7
    assert all(entry['recipe_version'] == 'managed-candidate.v1' for entry in version.provenance['recipes'][1:])
    detail = service.detail(OWNER, repo.plans[0].id)
    assert len(detail.report.meals[1].items) == 3
    assert detail.totals.energy_kcal == Decimal('1480')
    with pytest.raises(ValidationError):
        PlanArchiveWrite(**(payload | {'component_recipes': ()}))
