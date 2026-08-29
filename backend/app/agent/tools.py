"""Tool adapter boundary between graph orchestration and deterministic nutrition services."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from sqlalchemy.orm import Session

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


class SessionNutritionToolAdapter:
    """Build a short-lived read session per deterministic tool invocation.

    A graph still receives only the narrow tool port; SQLAlchemy remains encapsulated in this
    infrastructure adapter and never leaks into graph nodes.
    """

    def __init__(self, *, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _service(self) -> tuple[Session, NutritionService]:
        from app.nutrition.repository import SqlAlchemyNutritionRepository

        session = self._session_factory()
        return session, NutritionService(repository=SqlAlchemyNutritionRepository(session))

    def search_food_catalog(self, request: FoodSearchInput) -> FoodSearchResult:
        session, service = self._service()
        try:
            return service.search_food_catalog(request)
        finally:
            session.close()

    def calculate_nutrition(
        self, request: NutritionCalculationInput
    ) -> NutritionCalculationResult:
        session, service = self._service()
        try:
            return service.calculate_nutrition(request)
        finally:
            session.close()

    def validate_nutrition_result(
        self, request: NutritionValidationInput
    ) -> NutritionValidationResult:
        session, service = self._service()
        try:
            return service.validate_nutrition_result(request)
        finally:
            session.close()
