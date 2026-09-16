"""Versioned archive DTOs; neither graph state nor provider payloads are accepted."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.planning.schemas import MealSlot, PlanningNutritionValues, REQUIRED_MEAL_SLOTS, TargetRange


class ArchiveDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, from_attributes=True)


class PlanTarget(ArchiveDTO):
    energy_kcal: TargetRange
    carbohydrate_g: TargetRange
    protein_g: TargetRange
    fat_g: TargetRange


class PlanMealItemSnapshot(ArchiveDTO):
    meal_role: Literal["staple", "protein", "vegetable"]
    display_name: str = Field(min_length=1, max_length=200)
    portion_description: str = Field(min_length=1, max_length=120)
    portion_grams: str = Field(pattern=r"^\d+(?:\.\d+)?$")
    method_tags: tuple[str, ...]
    flavour_tags: tuple[str, ...]
    nutrients: PlanningNutritionValues


class PlanMealSnapshot(ArchiveDTO):
    slot: MealSlot
    display_name: str = Field(min_length=1, max_length=200)
    portion_description: str = Field(min_length=1, max_length=120)
    portion_grams: str = Field(pattern=r"^\d+(?:\.\d+)?$")
    method_tags: tuple[str, ...]
    flavour_tags: tuple[str, ...]
    matched_preference_summaries: tuple[str, ...]
    matched_exclusion_summaries: tuple[str, ...]
    nutrients: PlanningNutritionValues
    items: tuple[PlanMealItemSnapshot, ...] = Field(default=(), max_length=3)

    @model_validator(mode="after")
    def checks_bundle_snapshot(self) -> "PlanMealSnapshot":
        if self.items:
            if self.slot not in {MealSlot.LUNCH, MealSlot.DINNER} or tuple(item.meal_role for item in self.items) != ("staple", "protein", "vegetable"):
                raise ValueError("invalid component meal structure")
            if any(not 0 < Decimal(item.portion_grams) <= 2000 for item in self.items):
                raise ValueError("component portions must be positive")
            if sum((Decimal(item.portion_grams) for item in self.items), Decimal(0)) != Decimal(self.portion_grams):
                raise ValueError("component grams do not match snapshot")
            for metric in PlanningNutritionValues.model_fields:
                if sum((getattr(item.nutrients, metric) for item in self.items), Decimal(0)) != getattr(self.nutrients, metric):
                    raise ValueError("component nutrients do not match snapshot")
        return self


class PlanRangeStatus(ArchiveDTO):
    energy_kcal: Literal["low", "in_range", "high"]
    carbohydrate_g: Literal["low", "in_range", "high"]
    protein_g: Literal["low", "in_range", "high"]
    fat_g: Literal["low", "in_range", "high"]


class PlanRelaxation(ArchiveDTO):
    metric: Literal["energy_kcal", "carbohydrate_g", "protein_g", "fat_g"]
    original_range: TargetRange
    plan_value: str = Field(pattern=r"^\d+(?:\.\d+)?$")
    deviation: str = Field(pattern=r"^-?\d+(?:\.\d+)?$")
    reason: str = Field(min_length=1, max_length=500)


class PlanAdjustment(ArchiveDTO):
    changed_slots: tuple[MealSlot, ...] = Field(min_length=1, max_length=1)
    matched_constraint: str = Field(min_length=1, max_length=200)
    range_status: PlanRangeStatus
    relaxation: PlanRelaxation | None = None


class PlanReport(ArchiveDTO):
    stage: Literal["complete"]
    target: PlanTarget
    meals: tuple[PlanMealSnapshot, ...] = Field(min_length=3, max_length=4)
    disclaimer: Literal["普通饮食参考，不替代医疗建议。"]
    adjustment: PlanAdjustment | None = None
    relaxation: PlanRelaxation | None = None

    @model_validator(mode="after")
    def ordered_slots(self) -> PlanReport:
        slots = [meal.slot for meal in self.meals]
        if slots[:3] != list(REQUIRED_MEAL_SLOTS) or (len(slots) == 4 and slots[3] is not MealSlot.SNACK):
            raise ValueError("archive requires ordered breakfast, lunch and dinner")
        return self


class PlanComponentRecipeEvidence(ArchiveDTO):
    recipe_id: uuid.UUID
    source_kind: Literal["managed_recipe_candidate"] = "managed_recipe_candidate"
    recipe_version: str = Field(min_length=1, max_length=80)
    catalog_version: str = Field(min_length=1, max_length=80)
    audit_version: str = Field(min_length=1, max_length=80)


class PlanArchiveWrite(ArchiveDTO):
    """Internal completion command, constructed only after deterministic validation."""

    user_id: uuid.UUID
    run_id: uuid.UUID
    thread_id: uuid.UUID
    started_at: datetime
    report: PlanReport
    recipe_ids: tuple[uuid.UUID, ...] = Field(min_length=3, max_length=10)
    component_recipes: tuple[PlanComponentRecipeEvidence, ...] = Field(default=(), max_length=9)
    target_version: str = Field(min_length=1, max_length=80)
    formula_version: str = Field(min_length=1, max_length=80)
    graph_version: str = Field(min_length=1, max_length=80)
    tool_version: str = Field(min_length=1, max_length=80)


    @model_validator(mode="after")
    def checks_component_evidence(self) -> "PlanArchiveWrite":
        evidence_ids = [item.recipe_id for item in self.component_recipes]
        if len(set(self.recipe_ids)) != len(self.recipe_ids) or len(set(evidence_ids)) != len(evidence_ids) or not set(evidence_ids).issubset(self.recipe_ids):
            raise ValueError("invalid component recipe evidence")
        if len(evidence_ids) != sum(len(meal.items) for meal in self.report.meals):
            raise ValueError("all components require frozen provenance")
        return self


class SavedPlanSummary(ArchiveDTO):
    id: uuid.UUID
    plan_date: date
    time_zone: str
    current_version: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime


class SavedPlan(SavedPlanSummary):
    version: int = Field(ge=1)
    saved_at: datetime
    report: PlanReport
    totals: PlanningNutritionValues
    adjustment_thread_id: uuid.UUID | None


class TodayPlan(ArchiveDTO):
    time_zone: str | None
    today: date | None
    plan: SavedPlan | None


class PlanHistoryPage(ArchiveDTO):
    items: tuple[SavedPlanSummary, ...]
    next_before: date | None
