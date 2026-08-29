"""Tool adapter boundary between graph orchestration and deterministic nutrition services."""

from __future__ import annotations

from typing import Protocol

from app.nutrition.schemas import (
    FoodSearchInput,
    FoodSearchResult,
    NutritionCalculationInput,
    NutritionCalculationResult,
    NutritionValidationInput,
    NutritionValidationResult,
)
from app.nutrition.service import NutritionService


class NutritionToolAdapter(Protocol):
    """The graph's complete nutrition authority; it never receives a Repository."""

    def search_food_catalog(self, request: FoodSearchInput) -> FoodSearchResult: ...

    def calculate_nutrition(
        self, request: NutritionCalculationInput
    ) -> NutritionCalculationResult: ...

    def validate_nutrition_result(
        self, request: NutritionValidationInput
    ) -> NutritionValidationResult: ...


class NutritionServiceToolAdapter:
    """Adapter keeps graph imports stable if the nutrition implementation evolves."""

    def __init__(self, *, service: NutritionService) -> None:
        self._service = service

    def search_food_catalog(self, request: FoodSearchInput) -> FoodSearchResult:
        return self._service.search_food_catalog(request)

    def calculate_nutrition(
        self, request: NutritionCalculationInput
    ) -> NutritionCalculationResult:
        return self._service.calculate_nutrition(request)

    def validate_nutrition_result(
        self, request: NutritionValidationInput
    ) -> NutritionValidationResult:
        return self._service.validate_nutrition_result(request)
