"""Pure, deterministic target-policy.v1 and safe plan-validation entry points."""

from __future__ import annotations

from decimal import Decimal

from app.planning.ports import PlanningNutritionPort, PlanningRepository
from app.planning.schemas import (
    ACTIVITY_FACTORS,
    HEALTH_REFUSAL_MESSAGE,
    DailyTarget,
    FormulaVariant,
    PlanValidationAction,
    PlanValidationResult,
    PlanningGoal,
    PlanningProfileInput,
    PreferenceReview,
    TargetCalculationResult,
    TargetRange,
)


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
