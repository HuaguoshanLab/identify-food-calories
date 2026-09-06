"""Versioned archive DTOs; neither graph state nor provider payloads are accepted."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.planning.schemas import MealSlot, PlanningNutritionValues, TargetRange


class ArchiveDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, from_attributes=True)


class PlanTarget(ArchiveDTO):
    energy_kcal: TargetRange
    carbohydrate_g: TargetRange
    protein_g: TargetRange
    fat_g: TargetRange


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
    meals: tuple[PlanMealSnapshot, ...] = Field(min_length=3, max_length=3)
    disclaimer: Literal["普通饮食参考，不替代医疗建议。"]
    adjustment: PlanAdjustment | None = None
    relaxation: PlanRelaxation | None = None

    @model_validator(mode="after")
    def ordered_slots(self) -> PlanReport:
        if [meal.slot for meal in self.meals] != list(MealSlot):
            raise ValueError("archive requires ordered breakfast, lunch and dinner")
        return self


class PlanArchiveWrite(ArchiveDTO):
    """Internal completion command, constructed only after deterministic validation."""

    user_id: uuid.UUID
    run_id: uuid.UUID
    thread_id: uuid.UUID
    started_at: datetime
    report: PlanReport
    recipe_ids: tuple[uuid.UUID, ...] = Field(min_length=3, max_length=3)
    target_version: str = Field(min_length=1, max_length=80)
    formula_version: str = Field(min_length=1, max_length=80)
    graph_version: str = Field(min_length=1, max_length=80)
    tool_version: str = Field(min_length=1, max_length=80)


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
