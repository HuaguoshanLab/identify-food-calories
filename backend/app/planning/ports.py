"""Narrow persistence and nutrition capabilities used by deterministic planning."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from app.nutrition.schemas import NutritionCalculationInput, NutritionCalculationResult
from app.planning.models import PlanningCompletionProjection, PlanningProfile
from app.planning.schemas import ControlledRecipe, MealSlot, DailyTarget, ManagedRecipeCandidate, PlanningProfileInput


class PlanningRepository(Protocol):
    """Future profile and recipe adapters; no SQLAlchemy Session crosses this boundary."""

    def get_planning_profile(self, *, user_id: uuid.UUID) -> PlanningProfileInput | None: ...

    def list_controlled_recipes(
        self, *, catalog_version: str | None, recipe_version: str,
        meal_slot: MealSlot | None = None, after_id: uuid.UUID | None = None,
        limit: int | None = None,
    ) -> list[ControlledRecipe]: ...

    def has_managed_recipe_candidates(self) -> bool: ...

    def list_managed_recipe_candidates(
        self, *, catalog_version: str | None,
        meal_slot: MealSlot | None = None, after_id: uuid.UUID | None = None,
        limit: int | None = None, food_ids: tuple[uuid.UUID, ...] | None = None,
        recipe_id: uuid.UUID | None = None, recipe_revision: int | None = None,
        include_components: bool = False,
    ) -> list[ManagedRecipeCandidate]: ...

    def list_recent_recipe_ids(
        self, *, user_id: uuid.UUID, plan_limit: int
    ) -> tuple[uuid.UUID, ...]: ...


class PlanningProfileRepository(Protocol):
    """Persistence port for explicit profile CRUD; every lookup is tenant-filtered."""

    def get_profile_for_user(self, *, user_id: uuid.UUID, for_update: bool = False) -> PlanningProfile | None: ...

    def add_profile(self, profile: PlanningProfile) -> PlanningProfile: ...


class PlanningCompletionProjectionRepository(PlanningProfileRepository, Protocol):
    """Planning-owned projection persistence; all lookups keep tenant proof in the port."""

    def add_completion_projection(
        self, projection: PlanningCompletionProjection
    ) -> PlanningCompletionProjection: ...

    def get_completion_projection_for_run_for_user(
        self, *, user_id: uuid.UUID, run_id: uuid.UUID, for_update: bool = False
    ) -> PlanningCompletionProjection | None: ...

    def get_completion_projection_for_user(
        self, *, user_id: uuid.UUID, for_update: bool = False
    ) -> PlanningCompletionProjection | None: ...

    def revoke_completion_projection_for_user(
        self, *, user_id: uuid.UUID, reason: str, revoked_at: datetime
    ) -> bool: ...


class PlanningCompletionProjectionWriter(Protocol):
    """Agent completion boundary writes a target fact without receiving planning ORM access."""

    def record_validated_completion(
        self, *, user_id: uuid.UUID, run_id: uuid.UUID, thread_id: uuid.UUID, target: DailyTarget,
        source_profile: PlanningProfileInput,
    ) -> PlanningCompletionProjection | None: ...


class PlanningNutritionPort(Protocol):
    """Narrow deterministic calculator used for each qualified recipe ingredient."""

    def calculate_nutrition(
        self, request: NutritionCalculationInput
    ) -> NutritionCalculationResult: ...
