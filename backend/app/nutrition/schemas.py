"""Runtime-validated contracts for deterministic nutrition tools.

These DTOs deliberately do not reuse ORM models, API responses, provider DTOs, or
LangGraph state.  A catalog record can be independently replayed by a service
without a model deciding any nutrition value.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


TOOL_VERSION = "nutrition-tools-v1"
CALCULATION_RULE_VERSION = "per-100g-v1"
MAX_CATALOG_CANDIDATES = 3
MAX_CANDIDATE_PORTION_HINTS = 3
RETRIEVAL_VERSION = "hybrid-food-retrieval-v1"


class NutritionAction(str, Enum):
    """Closed actions consumed by graph routing, never reinterpreted by a model."""

    RECALCULATE = "RECALCULATE"
    ASK = "ASK"
    BLOCK = "BLOCK"
    WARN = "WARN"
    PASS = "PASS"


class FoodRelation(str, Enum):
    """Controlled, user-readable relation labels for non-exact candidates."""

    NAME_VARIANT = "名称相近"
    REGIONAL_PREPARATION_VARIANT = "地域/做法变体"
    SAME_CLASS = "同类食物"


class NutritionValues(BaseModel):
    """Internal, unrounded nutrients for an edible 100g base or calculated item."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    energy_kcal: Decimal
    protein_g: Decimal
    fat_g: Decimal
    carbohydrate_g: Decimal


class ControlledPortion(BaseModel):
    """A food-specific, versioned and auditable conversion to grams."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    description: str = Field(min_length=1, max_length=120)
    grams: Decimal = Field(gt=0)
    source_reference: str = Field(min_length=1, max_length=500)
    version: str = Field(min_length=1, max_length=80)
    audited: bool = True


class QualifiedFood(BaseModel):
    """The only catalog representation deterministic tools are allowed to use."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    canonical_name: str = Field(min_length=1, max_length=200)
    catalog_version: str = Field(min_length=1, max_length=80)
    prepared_state: str = Field(min_length=1, max_length=120)
    source_name: str = Field(min_length=1, max_length=120)
    source_url: str = Field(min_length=1, max_length=500)
    license_name: str = Field(min_length=1, max_length=120)
    aliases: tuple[str, ...] = ()
    portions: tuple[ControlledPortion, ...] = ()
    nutrients_per_100g: NutritionValues

    @model_validator(mode="after")
    def requires_calculable_nutrients(self) -> QualifiedFood:
        """Qualification prevents partial source records from silently becoming zero."""

        if any(
            value < 0
            for value in (
                self.nutrients_per_100g.energy_kcal,
                self.nutrients_per_100g.protein_g,
                self.nutrients_per_100g.fat_g,
                self.nutrients_per_100g.carbohydrate_g,
            )
        ):
            raise ValueError("qualified food nutrients cannot be negative")
        return self


class FoodSearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    query: str = Field(min_length=1, max_length=200)


class FoodSearchEvidence(BaseModel):
    """Internal channel evidence; it must never cross a public boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    food: QualifiedFood
    relation: FoodRelation
    text_rank: int | None = Field(default=None, gt=0)
    vector_rank: int | None = Field(default=None, gt=0)
    text_score: Decimal | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    vector_score: Decimal | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)

    @model_validator(mode="after")
    def requires_ranked_channel_evidence(self) -> FoodSearchEvidence:
        if self.text_rank is None and self.vector_rank is None:
            raise ValueError("search evidence requires at least one ranked channel")
        if self.text_rank is None and self.text_score is not None:
            raise ValueError("text score requires a text rank")
        if self.vector_rank is None and self.vector_score is not None:
            raise ValueError("vector score requires a vector rank")
        return self


class FoodSearchCandidate(BaseModel):
    """Allowlisted public projection; scores and provider evidence stay internal."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    food_id: uuid.UUID
    catalog_version: str = Field(min_length=1, max_length=80)
    canonical_name: str = Field(min_length=1, max_length=200)
    relation: FoodRelation
    prepared_state: str | None = Field(default=None, min_length=1, max_length=120)
    portion_hints: tuple[str, ...] = Field(default=(), max_length=MAX_CANDIDATE_PORTION_HINTS)
    source_name: str = Field(min_length=1, max_length=120)


class FoodSearchFusionResult(BaseModel):
    """Non-exact fusion is always a confirmation boundary, never an authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    action: NutritionAction = NutritionAction.ASK
    selected_food: None = None
    candidates: tuple[FoodSearchCandidate, ...] = Field(
        default=(), max_length=MAX_CATALOG_CANDIDATES
    )
    retrieval_version: str = Field(default=RETRIEVAL_VERSION, min_length=1, max_length=80)

    @model_validator(mode="after")
    def rejects_nonexact_selection(self) -> FoodSearchFusionResult:
        if self.action is not NutritionAction.ASK:
            raise ValueError("fused non-exact search results must ask for confirmation")
        return self


class FoodSearchResult(BaseModel):
    """The resolved exact authority or safe non-exact candidate summaries.

    Non-exact candidates retain the deterministic relation that explains why
    they were offered.  They are not authority records and cannot calculate
    nutrition without the later ID/version re-read.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    action: NutritionAction
    query: str
    selected_food: QualifiedFood | None = None
    candidates: tuple[FoodSearchCandidate, ...] = Field(
        default=(), max_length=MAX_CATALOG_CANDIDATES
    )
    safe_message: str

    @model_validator(mode="after")
    def enforces_resolution_contract(self) -> FoodSearchResult:
        if self.action is NutritionAction.PASS and self.selected_food is None:
            raise ValueError("a PASS search result requires one selected food")
        if self.action is not NutritionAction.PASS and self.selected_food is not None:
            raise ValueError("only PASS may select a food")
        if self.action is NutritionAction.PASS and self.candidates:
            raise ValueError("a PASS search result must not expose candidates")
        return self


class NutritionCalculationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    food_id: uuid.UUID
    catalog_version: str = Field(min_length=1, max_length=80)
    grams: Decimal | None = None
    portion_description: str | None = Field(default=None, min_length=1, max_length=120)


class NutritionCalculationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action: NutritionAction
    food: QualifiedFood | None = None
    grams: Decimal | None = None
    nutrients: NutritionValues | None = None
    calculation_rule_version: str = CALCULATION_RULE_VERSION
    safe_message: str

    @model_validator(mode="after")
    def keeps_partial_and_completed_results_unambiguous(self) -> NutritionCalculationResult:
        has_nutrition = self.food is not None and self.grams is not None and self.nutrients is not None
        if self.action is NutritionAction.PASS and not has_nutrition:
            raise ValueError("a PASS calculation requires food, grams, and nutrients")
        if self.action is not NutritionAction.PASS and has_nutrition:
            raise ValueError("only PASS may expose calculated nutrition")
        return self


class NutritionValidationInput(BaseModel):
    """An unrounded item and optional caller-provided total for deterministic checks."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    calculation: NutritionCalculationResult
    reported_total: NutritionValues | None = None


class NutritionValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action: NutritionAction
    rule_id: str = Field(min_length=1, max_length=100)
    rule_version: str = CALCULATION_RULE_VERSION
    safe_message: str
    food_id: uuid.UUID | None = None
