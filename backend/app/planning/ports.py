"""Narrow persistence and nutrition capabilities used by deterministic planning."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from app.nutrition.schemas import NutritionCalculationInput, NutritionCalculationResult
from app.planning.models import PlanningCompletionProjection, PlanningProfile
from app.planning.schemas import ControlledRecipe, DailyTarget, ManagedRecipeCandidate, PlanningProfileInput


class PlanningRepository(Protocol):
    """Future profile and recipe adapters; no SQLAlchemy Session crosses this boundary."""

    def get_planning_profile(self, *, user_id: uuid.UUID) -> PlanningProfileInput | None: ...

    def list_controlled_recipes(
        self, *, catalog_version: str, recipe_version: str
    ) -> list[ControlledRecipe]: ...

    def list_managed_recipe_candidates(
        self, *, catalog_version: str
    ) -> list[ManagedRecipeCandidate]: ...


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
        self, *, user_id: uuid.UUID, run_id: uuid.UUID, thread_id: uuid.UUID, target: DailyTarget
    ) -> PlanningCompletionProjection: ...


class PlanningNutritionPort(Protocol):
    """Narrow deterministic calculator used for each qualified recipe ingredient."""

    def calculate_nutrition(
        self, request: NutritionCalculationInput
    ) -> NutritionCalculationResult: ...
