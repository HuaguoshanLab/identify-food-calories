"""Pure, deterministic target-policy.v1 and safe plan-validation entry points."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

from app.planning.models import PlanningProfile
from app.planning.ports import PlanningNutritionPort, PlanningProfileRepository, PlanningRepository
from app.planning.schemas import (
    ACTIVITY_FACTORS,
    HEALTH_REFUSAL_MESSAGE,
    DailyTarget,
    MealCompositionResult,
    MealSlot,
    FormulaVariant,
    PlanValidationAction,
    PlanValidationResult,
    PlannedMeal,
    PlanningNutritionValues,
    PlanningGoal,
    PlanningProfilePatch,
    PlanningProfileInput,
    PlanningProfileWrite,
    PreferenceReview,
    FORMULA_VERSION,
    TARGET_POLICY_VERSION,
    TargetCalculationResult,
    TargetRange,
)
from app.nutrition.schemas import NutritionAction, NutritionCalculationInput, NutritionValues


MIN_ADULT_AGE = 19
MAX_ADULT_AGE = 78
MIN_SAFE_ENERGY_KCAL = Decimal("1200")
TARGET_RANGE_MARGIN_KCAL = Decimal("100")
CARBOHYDRATE_AMDR = (Decimal("0.45"), Decimal("0.65"))
PROTEIN_AMDR = (Decimal("0.10"), Decimal("0.35"))
FAT_AMDR = (Decimal("0.20"), Decimal("0.35"))
SPEED_DELTAS: dict[str, Decimal] = {
    "maintain": Decimal("0"),
    "gradual_loss": Decimal("-250"),
    "gradual_gain": Decimal("200"),
}


class PlanningService:
    """Owns safety decisions so browsers, graphs, and models cannot calculate targets."""

    def __init__(
        self, *, repository: PlanningRepository, nutrition_port: PlanningNutritionPort
    ) -> None:
        self._repository = repository
        self._nutrition_port = nutrition_port

    def calculate_daily_target(
        self, profile: PlanningProfileInput, preferences: PreferenceReview
    ) -> TargetCalculationResult:
        """Return a target only after explicit confirmation and every safety guard passes."""

        if not self._has_complete_inputs(profile, preferences):
            return TargetCalculationResult(
                action=PlanValidationAction.NEEDS_INPUT,
                safe_message="请补全并确认身体资料、目标和饮食偏好后继续。",
            )
        if self._is_health_scope_blocked(profile):
            return TargetCalculationResult(
                action=PlanValidationAction.BLOCK_HEALTH_SCOPE,
                safe_message=HEALTH_REFUSAL_MESSAGE,
            )

        assert profile.height_cm is not None
        assert profile.weight_kg is not None
        assert profile.age_years is not None
        assert profile.formula_variant is not None
        assert profile.activity_level is not None
        assert profile.goal_speed is not None
        energy = (
            self._mifflin_st_jeor(profile)
            * ACTIVITY_FACTORS[profile.activity_level]
            + SPEED_DELTAS[profile.goal_speed]
        )
        energy_range = TargetRange(
            lower=energy - TARGET_RANGE_MARGIN_KCAL,
            upper=energy + TARGET_RANGE_MARGIN_KCAL,
        )
        if energy < MIN_SAFE_ENERGY_KCAL or energy_range.lower < MIN_SAFE_ENERGY_KCAL:
            return TargetCalculationResult(
                action=PlanValidationAction.BLOCK_HEALTH_SCOPE,
                safe_message=HEALTH_REFUSAL_MESSAGE,
            )

        return TargetCalculationResult(
            action=PlanValidationAction.PASS,
            target=DailyTarget(
                energy_kcal=energy_range,
                carbohydrate_g=self._macro_range(energy_range, CARBOHYDRATE_AMDR, Decimal("4")),
                protein_g=self._macro_range(energy_range, PROTEIN_AMDR, Decimal("4")),
                fat_g=self._macro_range(energy_range, FAT_AMDR, Decimal("9")),
            ),
            safe_message="每日目标区间已按版本化普通成人政策确定性计算。",
        )

    def validate_plan(
        self,
        *,
        target: DailyTarget,
        matched_exclusions: tuple[str, ...] = (),
        allow_target_relaxation: bool = False,
    ) -> PlanValidationResult:
        """Keep exclusions and health floors outside the only relaxable target dimensions."""

        if target.energy_kcal.lower < MIN_SAFE_ENERGY_KCAL:
            return PlanValidationResult(
                action=PlanValidationAction.BLOCK_HEALTH_SCOPE,
                rule_id="minimum-energy-floor",
                safe_message=HEALTH_REFUSAL_MESSAGE,
            )
        if matched_exclusions:
            return PlanValidationResult(
                action=PlanValidationAction.REPLAN,
                rule_id="confirmed-exclusion",
                safe_message="受控餐单包含已确认的排除项，不能放宽该约束。",
            )
        if allow_target_relaxation:
            return PlanValidationResult(
                action=PlanValidationAction.RELAX,
                rule_id="energy-or-macro-relaxation",
                relaxed_metric="energy_or_macro",
                safe_message="可在保留已确认排除项和健康边界的前提下调整能量或宏量目标。",
            )
        return PlanValidationResult(
            action=PlanValidationAction.PASS,
            rule_id="planning-validation-pass",
            safe_message="餐单通过确定性目标与约束校验。",
        )

    def compose_daily_meals(
        self, *, catalog_version: str, preferences: PreferenceReview, exclude_recipe_ids: tuple[uuid.UUID, ...] = ()
    ) -> MealCompositionResult:
        """Select one fully qualified candidate per stable slot and recompute every ingredient."""

        if not preferences.confirmed:
            return MealCompositionResult(
                action=PlanValidationAction.NEEDS_INPUT,
                safe_message="请先确认本次要使用的忌口和口味偏好。",
            )
        recipes = self._repository.list_controlled_recipes(catalog_version=catalog_version)
        meals: list[PlannedMeal] = []
        for slot in MealSlot:
            meal = next(
                (
                    built_meal
                    for recipe in recipes
                    if slot in recipe.meal_slots
                    and recipe.catalog_version == catalog_version
                    and recipe.id not in exclude_recipe_ids
                    and not self._matches_exclusion(recipe=recipe, exclusions=preferences.exclusions)
                    and (
                        built_meal := self._build_meal(
                            recipe=recipe,
                            slot=slot,
                            preferences=preferences,
                        )
                    )
                    is not None
                ),
                None,
            )
            if meal is None:
                return MealCompositionResult(
                    action=PlanValidationAction.REPLAN,
                    safe_message="没有同时满足受控来源、审核、目录资格和三餐槽位的候选。",
                )
            meals.append(meal)
        return MealCompositionResult(
            action=PlanValidationAction.PASS,
            meals=tuple(meals),
            safe_message="三餐营养值已由合格目录条目和受控克数重新计算。",
        )

    def _build_meal(self, *, recipe, slot: MealSlot, preferences: PreferenceReview) -> PlannedMeal | None:
        calculated: list[NutritionValues] = []
        for ingredient in recipe.ingredients:
            calculation = self._nutrition_port.calculate_nutrition(
                NutritionCalculationInput(
                    food_id=ingredient.food_id,
                    catalog_version=ingredient.catalog_version,
                    grams=ingredient.grams,
                )
            )
            if calculation.action is not NutritionAction.PASS:
                return None
            assert calculation.food is not None
            assert calculation.nutrients is not None
            if any(
                exclusion.casefold() in calculation.food.canonical_name.casefold()
                for exclusion in preferences.exclusions
            ):
                return None
            calculated.append(calculation.nutrients)
        if not calculated:
            return None
        preference_summaries = tuple(
            f"偏好：{preference}"
            for preference in self._matching_preferences(recipe=recipe, preferences=preferences)
        )
        return PlannedMeal(
            slot=slot,
            recipe_id=recipe.id,
            display_name=recipe.display_name,
            portion_description=recipe.portion_description,
            portion_grams=recipe.portion_grams,
            method_tags=recipe.method_tags,
            flavour_tags=recipe.flavour_tags,
            matched_preference_summaries=preference_summaries,
            matched_exclusion_summaries=(),
            nutrients=PlanningNutritionValues(
                energy_kcal=sum((value.energy_kcal for value in calculated), Decimal("0")),
                protein_g=sum((value.protein_g for value in calculated), Decimal("0")),
                fat_g=sum((value.fat_g for value in calculated), Decimal("0")),
                carbohydrate_g=sum(
                    (value.carbohydrate_g for value in calculated), Decimal("0")
                ),
            ),
        )

    @staticmethod
    def _matches_exclusion(*, recipe, exclusions: tuple[str, ...]) -> bool:
        searchable = " ".join(
            (recipe.display_name, *recipe.method_tags, *recipe.flavour_tags)
        ).casefold()
        return any(exclusion.casefold() in searchable for exclusion in exclusions)

    @staticmethod
    def _matching_preferences(*, recipe, preferences: PreferenceReview) -> tuple[str, ...]:
        # The public card only claims a preference when it is literally present in controlled tags.
        return tuple(
            preference
            for preference in preferences.taste_preferences
            if preference.casefold() in {tag.casefold() for tag in recipe.flavour_tags}
        )

    @staticmethod
    def _has_complete_inputs(profile: PlanningProfileInput, preferences: PreferenceReview) -> bool:
        return all(
            (
                profile.height_cm is not None,
                profile.weight_kg is not None,
                profile.age_years is not None,
                profile.formula_variant is not None,
                profile.activity_level is not None,
                profile.goal is not None,
                profile.goal_speed is not None,
                preferences.confirmed,
            )
        )

    @staticmethod
    def _is_health_scope_blocked(profile: PlanningProfileInput) -> bool:
        return any(
            (
                profile.age_years is not None
                and not MIN_ADULT_AGE <= profile.age_years <= MAX_ADULT_AGE,
                profile.is_pregnant_or_breastfeeding,
                profile.has_disease_or_treatment,
                profile.uses_medication,
                profile.has_eating_disorder_or_self_harm_risk,
                profile.has_extreme_weight_control_goal,
                profile.goal not in {PlanningGoal.MAINTAIN, PlanningGoal.LOSS, PlanningGoal.GAIN},
                profile.goal_speed not in SPEED_DELTAS,
            )
        )

    @staticmethod
    def _mifflin_st_jeor(profile: PlanningProfileInput) -> Decimal:
        """Use the explicit selected variant; it is a formula parameter, not an identity claim."""

        assert profile.weight_kg is not None
        assert profile.height_cm is not None
        assert profile.age_years is not None
        assert profile.formula_variant is not None
        base = (
            Decimal("10") * profile.weight_kg
            + Decimal("6.25") * profile.height_cm
            - Decimal("5") * Decimal(profile.age_years)
        )
        if profile.formula_variant is FormulaVariant.MIFFLIN_ST_JEOR_MALE:
            return base + Decimal("5")
        return base - Decimal("161")

    @staticmethod
    def _macro_range(
        energy: TargetRange, percentage: tuple[Decimal, Decimal], kcal_per_gram: Decimal
    ) -> TargetRange:
        return TargetRange(
            lower=energy.lower * percentage[0] / kcal_per_gram,
            upper=energy.upper * percentage[1] / kcal_per_gram,
        )


class PlanningProfileUnavailable(LookupError):
    """Uniform missing, foreign, and deleted profile result."""


class PlanningProfileService:
    """Owns explicit profile save/delete transactions, not policy or memory preferences."""

    def __init__(self, *, repository: PlanningProfileRepository, now: Callable[[], datetime] | None = None, commit: Callable[[], None] | None = None, rollback: Callable[[], None] | None = None) -> None:
        self._repository = repository
        self._now = now or (lambda: datetime.now(UTC))
        self._commit = commit or (lambda: None)
        self._rollback = rollback or (lambda: None)

    def get_profile(self, *, user_id: uuid.UUID) -> PlanningProfile:
        profile = self._repository.get_profile_for_user(user_id=user_id)
        if profile is None:
            raise PlanningProfileUnavailable("planning profile is unavailable")
        return profile

    def replace_profile(self, *, user_id: uuid.UUID, payload: PlanningProfileWrite) -> PlanningProfile:
        profile = self._repository.get_profile_for_user(user_id=user_id, for_update=True)
        now = self._now()
        try:
            if profile is None:
                profile = PlanningProfile(
                    id=uuid.uuid4(), user_id=user_id, target_policy_version=TARGET_POLICY_VERSION,
                    formula_version=FORMULA_VERSION, created_at=now, updated_at=now, deleted_at=None,
                    **payload.model_dump(),
                )
                profile = self._repository.add_profile(profile)
            else:
                self._apply_payload(profile, payload.model_dump())
                profile.target_policy_version = TARGET_POLICY_VERSION
                profile.formula_version = FORMULA_VERSION
                profile.updated_at = now
            self._commit()
            return profile
        except Exception:
            self._rollback()
            raise

    def update_profile(self, *, user_id: uuid.UUID, payload: PlanningProfilePatch) -> PlanningProfile:
        profile = self._repository.get_profile_for_user(user_id=user_id, for_update=True)
        if profile is None:
            raise PlanningProfileUnavailable("planning profile is unavailable")
        try:
            self._apply_payload(profile, payload.model_dump(exclude_unset=True))
            profile.updated_at = self._now()
            self._commit()
            return profile
        except Exception:
            self._rollback()
            raise

    def delete_profile(self, *, user_id: uuid.UUID) -> None:
        profile = self._repository.get_profile_for_user(user_id=user_id, for_update=True)
        if profile is None:
            raise PlanningProfileUnavailable("planning profile is unavailable")
        now = self._now()
        try:
            profile.deleted_at = now
            profile.updated_at = now
            self._commit()
        except Exception:
            self._rollback()
            raise

    @staticmethod
    def _apply_payload(profile: PlanningProfile, values: dict[str, object]) -> None:
        for field, value in values.items():
            setattr(profile, field, value.value if hasattr(value, "value") else value)
