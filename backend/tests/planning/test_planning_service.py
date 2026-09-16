"""Fake-port contracts for deterministic, non-medical diet planning."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.planning.schemas import (
    ACTIVITY_FACTORS,
    CONTROLLED_RECIPE_VERSION,
    HEALTH_REFUSAL_MESSAGE,
    TARGET_POLICY_VERSION,
    ActivityLevel,
    ControlledRecipe,
    ControlledRecipeIngredient,
    ManagedRecipeCandidate,
    ManagedRecipeCandidateStatus,
    DailyTarget,
    MealSlot,
    REQUIRED_MEAL_SLOTS,
    PlanValidationAction,
    PlannedMeal,
    PlanningNutritionValues,
    PlanningProfileInput,
    PreferenceReview,
)
from app.planning.service import PlanningService
from app.nutrition.schemas import (
    NutritionCalculationInput,
    NutritionValues,
    QualifiedFood,
)
from app.nutrition.service import NutritionService


class FakePlanningRepository:
    """Records recipe access so health guards prove they run before retrieval."""

    def __init__(self, recipes: list[ControlledRecipe] | None = None, candidates: list[ManagedRecipeCandidate] | None = None, recent_recipe_ids: tuple[uuid.UUID, ...] = ()) -> None:
        self.recipe_search_calls = 0
        self.recipes = recipes or []
        self.candidates = candidates or []
        self.recent_recipe_ids = recent_recipe_ids

    def list_controlled_recipes(
        self, *, catalog_version: str | None, recipe_version: str,
        meal_slot=None, after_id=None, limit=None,
    ) -> list[ControlledRecipe]:
        self.recipe_search_calls += 1
        rows = [recipe for recipe in self.recipes if recipe.recipe_version == recipe_version
                and (catalog_version is None or recipe.catalog_version == catalog_version)
                and (meal_slot is None or meal_slot in recipe.meal_slots)
                and (after_id is None or recipe.id > after_id)]
        return sorted(rows, key=lambda row: row.id)[:limit]

    def has_managed_recipe_candidates(self):
        return bool(self.candidates)

    def list_managed_recipe_candidates(
        self, *, catalog_version: str | None, meal_slot=None, after_id=None,
        limit=None, food_ids=None, recipe_id=None, recipe_revision=None, include_components=False,
    ) -> list[ManagedRecipeCandidate]:
        rows = [candidate for candidate in self.candidates
                if (catalog_version is None or candidate.catalog_version == catalog_version)
                and (meal_slot is None or candidate.meal_slot is meal_slot)
                and (after_id is None or candidate.id > after_id)
                and (food_ids is None or candidate.nutrition_item_id in food_ids)
                and (recipe_id is None or candidate.id == recipe_id)
                and (recipe_revision is None or candidate.revision == recipe_revision)]
        return sorted(rows, key=lambda row: row.id)[:limit]

    def list_recent_recipe_ids(self, *, user_id: uuid.UUID, plan_limit: int) -> tuple[uuid.UUID, ...]:
        return self.recent_recipe_ids


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
        recipe_version=CONTROLLED_RECIPE_VERSION,
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


def managed_candidate(*, slot: MealSlot, food: QualifiedFood) -> ManagedRecipeCandidate:
    return ManagedRecipeCandidate(
        id=uuid.uuid4(), nutrition_item_id=food.id, catalog_version=food.catalog_version,
        display_name=food.canonical_name, meal_slot=slot, portion_grams=Decimal("180"),
        portion_description="一盘", method_tags=("炒",), flavour_tags=("家常",),
        status=ManagedRecipeCandidateStatus.ENABLED, revision=1,
    )


def validation_target() -> DailyTarget:
    return DailyTarget.model_validate(
        {
            "energy_kcal": {"lower": "1800", "upper": "2000"},
            "carbohydrate_g": {"lower": "202.5", "upper": "325"},
            "protein_g": {"lower": "45", "upper": "175"},
            "fat_g": {"lower": "40", "upper": "77.8"},
        }
    )


def planned_meal(
    *, slot: MealSlot, energy: str, carbohydrate: str, protein: str, fat: str,
    recipe_id: uuid.UUID | None = None,
) -> PlannedMeal:
    return PlannedMeal(
        slot=slot,
        recipe_id=recipe_id or uuid.uuid4(),
        display_name=f"{slot.value} 受控餐",
        portion_description="一份",
        portion_grams=Decimal("100"),
        method_tags=("快手",),
        flavour_tags=("清淡",),
        nutrients=PlanningNutritionValues(
            energy_kcal=Decimal(energy),
            carbohydrate_g=Decimal(carbohydrate),
            protein_g=Decimal(protein),
            fat_g=Decimal(fat),
        ),
    )


def valid_daily_meals() -> tuple[PlannedMeal, ...]:
    return (
        planned_meal(slot=MealSlot.BREAKFAST, energy="600", carbohydrate="80", protein="30", fat="20"),
        planned_meal(slot=MealSlot.LUNCH, energy="700", carbohydrate="90", protein="40", fat="20"),
        planned_meal(slot=MealSlot.DINNER, energy="600", carbohydrate="80", protein="30", fat="20"),
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

    target = validation_target()
    result = PlanningService(
        repository=FakePlanningRepository(), nutrition_port=FakeNutritionPort()
    ).validate_plan(
        target=target,
        meals=valid_daily_meals(),
        matched_exclusions=("香菜",),
        allow_target_relaxation=True,
    )

    assert result.action is PlanValidationAction.REPLAN
    assert result.safe_message == "受控餐单包含已确认的排除项，不能放宽该约束。"


def test_plan_validation_recomputes_daily_totals_and_macro_ratios_before_pass() -> None:
    service = PlanningService(repository=FakePlanningRepository(), nutrition_port=FakeNutritionPort())

    result = service.validate_plan(target=validation_target(), meals=valid_daily_meals())

    assert result.action is PlanValidationAction.PASS
    assert result.rule_id == "planning-validation-pass"


def test_plan_validation_rejects_out_of_range_totals_and_only_relaxes_target_dimensions() -> None:
    service = PlanningService(repository=FakePlanningRepository(), nutrition_port=FakeNutritionPort())
    too_low = tuple(
        planned_meal(
            slot=slot,
            energy="350",
            carbohydrate="50",
            protein="20",
            fat="15",
        )
            for slot in REQUIRED_MEAL_SLOTS
    )

    rejected = service.validate_plan(target=validation_target(), meals=too_low)

    assert rejected.action is PlanValidationAction.REPLAN
    assert rejected.rule_id == "minimum-plan-energy-floor"
    assert service.validate_plan(
        target=validation_target(), meals=too_low, allow_target_relaxation=True
    ).action is PlanValidationAction.REPLAN


def test_plan_validation_rejects_macro_ratio_and_duplicate_recipe_before_relaxation() -> None:
    service = PlanningService(repository=FakePlanningRepository(), nutrition_port=FakeNutritionPort())
    ratio_failure = (
        planned_meal(slot=MealSlot.BREAKFAST, energy="600", carbohydrate="80", protein="30", fat="13"),
        planned_meal(slot=MealSlot.LUNCH, energy="700", carbohydrate="90", protein="40", fat="14"),
        planned_meal(slot=MealSlot.DINNER, energy="600", carbohydrate="80", protein="30", fat="13"),
    )

    macro_result = service.validate_plan(target=validation_target(), meals=ratio_failure)

    assert macro_result.action is PlanValidationAction.REPLAN
    assert macro_result.rule_id == "fat_g-ratio-out-of-range"
    shared_recipe_id = uuid.uuid4()
    duplicate_result = service.validate_plan(
        target=validation_target(),
        meals=(
            planned_meal(slot=MealSlot.BREAKFAST, energy="600", carbohydrate="80", protein="30", fat="20", recipe_id=shared_recipe_id),
            planned_meal(slot=MealSlot.LUNCH, energy="700", carbohydrate="90", protein="40", fat="20", recipe_id=shared_recipe_id),
            planned_meal(slot=MealSlot.DINNER, energy="600", carbohydrate="80", protein="30", fat="20"),
        ),
        allow_target_relaxation=True,
    )

    assert duplicate_result.action is PlanValidationAction.REPLAN
    assert duplicate_result.rule_id == "duplicate-controlled-recipe"


def test_composition_never_reuses_a_multi_slot_recipe() -> None:
    food = qualified_food(name="测试食材", energy="600")
    recipe = controlled_recipe(slot=MealSlot.BREAKFAST, food=food, name="唯一受控餐").model_copy(
        update={"meal_slots": tuple(MealSlot)}
    )

    result = PlanningService(
        repository=FakePlanningRepository([recipe]), nutrition_port=RecipeNutritionPort([food])
    ).compose_daily_meals(catalog_version=CATALOG_VERSION, preferences=confirmed_preferences())

    assert result.action is PlanValidationAction.REPLAN
    assert result.meals == ()


def test_managed_candidates_are_used_without_a_hard_coded_catalog_version() -> None:
    foods = [qualified_food(name=f"候选{slot.value}", energy="200") for slot in REQUIRED_MEAL_SLOTS]
    candidates = [managed_candidate(slot=slot, food=food) for slot, food in zip(REQUIRED_MEAL_SLOTS, foods, strict=True)]

    result = PlanningService(
        repository=FakePlanningRepository(candidates=candidates),
        nutrition_port=RecipeNutritionPort(foods),
    ).compose_daily_meals(catalog_version=None, preferences=confirmed_preferences())

    assert result.action is PlanValidationAction.PASS
    assert [meal.display_name for meal in result.meals] == [food.canonical_name for food in foods]


def test_managed_candidates_avoid_recently_archived_meals_when_each_slot_has_an_alternative() -> None:
    foods = [qualified_food(name=f"{slot.value}旧菜", energy="200") for slot in REQUIRED_MEAL_SLOTS]
    alternatives = [qualified_food(name=f"{slot.value}新菜", energy="200") for slot in REQUIRED_MEAL_SLOTS]
    used = [managed_candidate(slot=slot, food=food) for slot, food in zip(REQUIRED_MEAL_SLOTS, foods, strict=True)]
    fresh = [managed_candidate(slot=slot, food=food) for slot, food in zip(REQUIRED_MEAL_SLOTS, alternatives, strict=True)]

    result = PlanningService(
        repository=FakePlanningRepository(candidates=[*used, *fresh], recent_recipe_ids=tuple(candidate.id for candidate in used)),
        nutrition_port=RecipeNutritionPort([*foods, *alternatives]),
    ).compose_daily_meals(user_id=uuid.uuid4(), catalog_version=None, preferences=confirmed_preferences())

    assert result.action is PlanValidationAction.PASS
    assert {meal.recipe_id for meal in result.meals}.isdisjoint({candidate.id for candidate in used})


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


def test_replaceable_food_identities_require_an_enabled_candidate_for_the_requested_slot() -> None:
    breakfast_food = qualified_food(name="早餐候选", energy="100")
    lunch_food = qualified_food(name="午餐候选", energy="150")
    current_food = qualified_food(name="当前午餐", energy="120")
    current = managed_candidate(slot=MealSlot.LUNCH, food=current_food)
    repository = FakePlanningRepository(candidates=[
        managed_candidate(slot=MealSlot.BREAKFAST, food=breakfast_food),
        managed_candidate(slot=MealSlot.LUNCH, food=lunch_food),
        current,
    ])
    service = PlanningService(
        repository=repository,
        nutrition_port=RecipeNutritionPort([breakfast_food, lunch_food, current_food]),
    )

    result = service.keep_replaceable_food_identities(
        identities=(
            (breakfast_food.id, breakfast_food.catalog_version),
            (lunch_food.id, lunch_food.catalog_version),
            (current_food.id, current_food.catalog_version),
        ),
        affected_slot=MealSlot.LUNCH,
        exclude_recipe_ids=(current.id,),
        preferences=confirmed_preferences(),
    )

    assert result == ((lunch_food.id, lunch_food.catalog_version),)


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
    assert result.failure_reason.value == "nutrition_unavailable"
    assert "营养数据当前不可用" in result.safe_message
    with pytest.raises(ValidationError):
        ControlledRecipe.model_validate({**recipe.model_dump(), "stored_total": {"energy_kcal": "1"}})


def test_explicit_recipe_selection_never_falls_back_after_revision_changes() -> None:
    foods = [qualified_food(name=f"候选{slot.value}", energy="200") for slot in REQUIRED_MEAL_SLOTS]
    candidates = [managed_candidate(slot=slot, food=food) for slot, food in zip(REQUIRED_MEAL_SLOTS, foods, strict=True)]
    selected = candidates[1].model_copy(update={"id": uuid.uuid4(), "portion_grams": Decimal("210")})
    repository = FakePlanningRepository(candidates=[*candidates, selected])
    service = PlanningService(repository=repository, nutrition_port=RecipeNutritionPort(foods))
    arguments = dict(catalog_version=None, preferences=confirmed_preferences(), required_food_id=selected.nutrition_item_id,
                     required_catalog_version=selected.catalog_version, required_slot=MealSlot.LUNCH,
                     required_recipe_id=selected.id, required_recipe_revision=selected.revision)
    result = service.compose_daily_meals(**arguments)
    assert result.action is PlanValidationAction.PASS
    assert result.meals[1].recipe_id == selected.id
    repository.candidates[-1] = selected.model_copy(update={"revision": 2})
    stale = service.compose_daily_meals(**arguments)
    assert stale.action is PlanValidationAction.NEEDS_INPUT
    assert stale.meals == ()
