"""Narrow persistence and nutrition capabilities used by deterministic planning."""

from __future__ import annotations

import uuid
from typing import Protocol

from app.planning.models import PlanningProfile
from app.planning.schemas import ControlledRecipe, PlanningProfileInput


class PlanningRepository(Protocol):
    """Future profile and recipe adapters; no SQLAlchemy Session crosses this boundary."""

    def get_planning_profile(self, *, user_id: uuid.UUID) -> PlanningProfileInput | None: ...

    def list_controlled_recipes(self, *, catalog_version: str) -> list[ControlledRecipe]: ...


class PlanningProfileRepository(Protocol):
    """Persistence port for explicit profile CRUD; every lookup is tenant-filtered."""

    def get_profile_for_user(self, *, user_id: uuid.UUID, for_update: bool = False) -> PlanningProfile | None: ...

    def add_profile(self, profile: PlanningProfile) -> PlanningProfile: ...


class PlanningNutritionPort(Protocol):
    """Future nutrition adapter used to recompute recipe totals from controlled foods."""

    def calculate_recipe_nutrients(self, *, recipe_id: str, catalog_version: str) -> object: ...
