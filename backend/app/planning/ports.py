"""Narrow persistence and nutrition capabilities used by deterministic planning."""

from __future__ import annotations

import uuid
from typing import Protocol

from app.planning.schemas import ControlledRecipe, PlanningProfileInput


class PlanningRepository(Protocol):
    """Future profile and recipe adapters; no SQLAlchemy Session crosses this boundary."""

    def get_planning_profile(self, *, user_id: uuid.UUID) -> PlanningProfileInput | None: ...

    def list_controlled_recipes(self, *, catalog_version: str) -> list[ControlledRecipe]: ...


class PlanningNutritionPort(Protocol):
    """Future nutrition adapter used to recompute recipe totals from controlled foods."""

    def calculate_recipe_nutrients(self, *, recipe_id: str, catalog_version: str) -> object: ...
