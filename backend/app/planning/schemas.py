"""Runtime-validated, non-medical public contracts for diet planning."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


TARGET_POLICY_VERSION = "target-policy.v1"
FORMULA_VERSION = "mifflin-st-jeor.v1"
CONTROLLED_RECIPE_LICENSE = "LicenseRef-Project-Authored-v1"
HEALTH_REFUSAL_MESSAGE = (
    "我们不能为你当前描述的情况生成个性化餐单。孕期或哺乳期、未成年人、疾病或用药、"
    "进食障碍或自伤，以及极端减重/增重目标需要专业评估。请咨询医生或注册营养师。"
)


class ActivityLevel(str, Enum):
    """The only five activity inputs accepted by target-policy.v1."""

    SEDENTARY = "sedentary"
    LIGHT = "light"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


ACTIVITY_FACTORS: dict[ActivityLevel, Decimal] = {
    ActivityLevel.SEDENTARY: Decimal("1.20"),
    ActivityLevel.LIGHT: Decimal("1.375"),
    ActivityLevel.MODERATE: Decimal("1.55"),
    ActivityLevel.HIGH: Decimal("1.725"),
    ActivityLevel.VERY_HIGH: Decimal("1.90"),
}


class FormulaVariant(str, Enum):
    """Explicit calculation variant; this field is never inferred from user data."""

    MIFFLIN_ST_JEOR_MALE = "mifflin_st_jeor_male"
    MIFFLIN_ST_JEOR_FEMALE = "mifflin_st_jeor_female"


class PlanningGoal(str, Enum):
    MAINTAIN = "maintain"
    LOSS = "loss"
    GAIN = "gain"


class PlanValidationAction(str, Enum):
    """Closed actions that graph routing may consume without reinterpretation."""

    PASS = "PASS"
    REPLAN = "REPLAN"
    RELAX = "RELAX"
    BLOCK_HEALTH_SCOPE = "BLOCK_HEALTH_SCOPE"
    NEEDS_INPUT = "NEEDS_INPUT"


class MealSlot(str, Enum):
    """The only stable meal-card positions exposed by the planning MVP."""

    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"


class PlanningProfileInput(BaseModel):
    """Transient profile data. Optional fields allow a safe NEEDS_INPUT response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    height_cm: Decimal | None = Field(default=None, ge=Decimal("100"), le=Decimal("250"))
    weight_kg: Decimal | None = Field(default=None, ge=Decimal("20"), le=Decimal("350"))
    age_years: int | None = Field(default=None, ge=1, le=130)
    formula_variant: FormulaVariant | None = None
    activity_level: ActivityLevel | None = None
    goal: PlanningGoal | None = None
    goal_speed: str | None = Field(default=None, min_length=1, max_length=80)
    is_pregnant_or_breastfeeding: bool = False
    has_disease_or_treatment: bool = False
    uses_medication: bool = False
    has_eating_disorder_or_self_harm_risk: bool = False
    has_extreme_weight_control_goal: bool = False


class PlanningProfileWrite(BaseModel):
    """The sole explicit persistence payload; preferences and health narratives stay elsewhere."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    height_cm: Decimal = Field(ge=Decimal("100"), le=Decimal("250"))
    weight_kg: Decimal = Field(ge=Decimal("20"), le=Decimal("350"))
    age_years: int = Field(ge=1, le=130)
    formula_variant: FormulaVariant
    activity_level: ActivityLevel
    goal: PlanningGoal
    goal_speed: Literal["maintain", "gradual_loss", "gradual_gain"]


class PlanningProfilePatch(BaseModel):
    """An explicit partial profile update; an empty patch must not become a silent no-op."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    height_cm: Decimal | None = Field(default=None, ge=Decimal("100"), le=Decimal("250"))
    weight_kg: Decimal | None = Field(default=None, ge=Decimal("20"), le=Decimal("350"))
    age_years: int | None = Field(default=None, ge=1, le=130)
    formula_variant: FormulaVariant | None = None
    activity_level: ActivityLevel | None = None
    goal: PlanningGoal | None = None
    goal_speed: Literal["maintain", "gradual_loss", "gradual_gain"] | None = None

    @model_validator(mode="after")
    def requires_at_least_one_change(self) -> PlanningProfilePatch:
        if not self.model_fields_set:
            raise ValueError("a profile patch requires at least one field")
        return self


class PlanningProfileResponse(PlanningProfileWrite):
    """Safe profile projection; deliberately omits identity, preferences, and health narratives."""

    model_config = ConfigDict(extra="forbid", frozen=True, from_attributes=True)

    target_policy_version: str = Field(min_length=1, max_length=80)
    formula_version: str = Field(min_length=1, max_length=80)

    @field_validator("height_cm", "weight_kg")
    @classmethod
    def renders_persisted_measurements_consistently(cls, value: Decimal) -> Decimal:
        # The PostgreSQL columns are fixed-scale, so every API path must expose that same scale.
        return value.quantize(Decimal("0.01"))


class PreferenceReview(BaseModel):
    """Planning may only use preferences after the user has explicitly reviewed them."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    confirmed: bool
    exclusions: tuple[str, ...] = ()
    taste_preferences: tuple[str, ...] = ()


class TargetRange(BaseModel):
    """Unrounded lower and upper values used by deterministic validation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lower: Decimal = Field(ge=0)
    upper: Decimal = Field(ge=0)

    @model_validator(mode="after")
    def has_ordered_bounds(self) -> TargetRange:
        if self.lower > self.upper:
            raise ValueError("target range lower bound cannot exceed upper bound")
        return self


class DailyTarget(BaseModel):
    """A safe public target range, never an exact medical prescription."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    energy_kcal: TargetRange
    carbohydrate_g: TargetRange
    protein_g: TargetRange
    fat_g: TargetRange
    policy_version: str = TARGET_POLICY_VERSION
    formula_version: str = FORMULA_VERSION


class ControlledRecipeIngredient(BaseModel):
    """A fixed quantity of one qualified catalog item, never a stored nutrient total."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    food_id: uuid.UUID
    catalog_version: str = Field(min_length=1, max_length=80)
    grams: Decimal = Field(gt=0, le=Decimal("2000"))
    portion_description: str = Field(min_length=1, max_length=120)


class ControlledRecipe(BaseModel):
    """Auditable recipe candidate with display-only details and qualified ingredients."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    stable_id: str = Field(min_length=1, max_length=120)
    display_name: str = Field(min_length=1, max_length=200)
    recipe_version: str = Field(min_length=1, max_length=80)
    catalog_version: str = Field(min_length=1, max_length=80)
    meal_slots: tuple[MealSlot, ...] = Field(min_length=1)
    portion_description: str = Field(min_length=1, max_length=120)
    portion_grams: Decimal = Field(gt=0, le=Decimal("2000"))
    method_tags: tuple[str, ...] = Field(min_length=1)
    flavour_tags: tuple[str, ...] = Field(min_length=1)
    ingredients: tuple[ControlledRecipeIngredient, ...] = Field(min_length=1)
    source_kind: str = "project_authored"
    source_reference: str = Field(min_length=1, max_length=500)
    license_name: str = CONTROLLED_RECIPE_LICENSE
    audit_status: str = "approved"
    audited_at: datetime
    audited_by_role: str = "nutrition_catalog_reviewer"
    audit_version: str = Field(min_length=1, max_length=80)
    is_active: bool = True

    @model_validator(mode="after")
    def is_a_qualified_project_recipe(self) -> ControlledRecipe:
        if self.source_kind != "project_authored":
            raise ValueError("controlled recipes must be project authored")
        if self.license_name != CONTROLLED_RECIPE_LICENSE:
            raise ValueError("controlled recipes require the project-authored license")
        if self.audit_status != "approved":
            raise ValueError("controlled recipes must be approved")
        if self.audited_by_role != "nutrition_catalog_reviewer":
            raise ValueError("controlled recipes require the authorized audit role")
        if not self.is_active:
            raise ValueError("controlled recipes must be active")
        if any(ingredient.catalog_version != self.catalog_version for ingredient in self.ingredients):
            raise ValueError("recipe ingredients must use the recipe catalog version")
        return self


class PlannedMeal(BaseModel):
    """Safe D-08 card payload; provenance and audit evidence remain server-side."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    slot: MealSlot
    recipe_id: uuid.UUID
    display_name: str = Field(min_length=1, max_length=200)
    portion_description: str = Field(min_length=1, max_length=120)
    portion_grams: Decimal = Field(gt=0)
    method_tags: tuple[str, ...]
    flavour_tags: tuple[str, ...]
    matched_preference_summaries: tuple[str, ...] = ()
    matched_exclusion_summaries: tuple[str, ...] = ()
    nutrients: "PlanningNutritionValues"


class PlanningNutritionValues(BaseModel):
    """Planning-owned public projection of the deterministic nutrition service result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    energy_kcal: Decimal = Field(ge=0)
    protein_g: Decimal = Field(ge=0)
    fat_g: Decimal = Field(ge=0)
    carbohydrate_g: Decimal = Field(ge=0)


class MealCompositionResult(BaseModel):
    """Closed composition response; incomplete safe candidates request deterministic replanning."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    action: PlanValidationAction
    meals: tuple[PlannedMeal, ...] = ()
    safe_message: str

    @model_validator(mode="after")
    def keeps_complete_meals_bound_to_pass(self) -> "MealCompositionResult":
        if self.action is PlanValidationAction.PASS and len(self.meals) != len(MealSlot):
            raise ValueError("a passing composition requires breakfast, lunch, and dinner")
        if self.action is not PlanValidationAction.PASS and self.meals:
            raise ValueError("only a passing composition may expose meals")
        return self


class TargetCalculationResult(BaseModel):
    """Action-bearing target calculation result with no raw profile disclosure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    action: PlanValidationAction
    target: DailyTarget | None = None
    policy_version: str = TARGET_POLICY_VERSION
    formula_version: str = FORMULA_VERSION
    safe_message: str

    @model_validator(mode="after")
    def keeps_target_visibility_unambiguous(self) -> TargetCalculationResult:
        if self.action is PlanValidationAction.PASS and self.target is None:
            raise ValueError("a passing target calculation requires a target")
        if self.action is not PlanValidationAction.PASS and self.target is not None:
            raise ValueError("only a passing target calculation may expose a target")
        return self


class PlanValidationResult(BaseModel):
    """Closed validation result consumed by graph routing and safe UI reporting."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    action: PlanValidationAction
    rule_id: str = Field(min_length=1, max_length=100)
    policy_version: str = TARGET_POLICY_VERSION
    safe_message: str
    relaxed_metric: str | None = None

    @model_validator(mode="after")
    def prevents_implicit_relaxation(self) -> PlanValidationResult:
        if self.action is PlanValidationAction.RELAX and self.relaxed_metric is None:
            raise ValueError("RELAX requires its affected metric")
        if self.action is not PlanValidationAction.RELAX and self.relaxed_metric is not None:
            raise ValueError("only RELAX may expose an affected metric")
        return self
