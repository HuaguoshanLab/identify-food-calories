"""Tool adapter boundary between graph orchestration and deterministic nutrition services."""

from __future__ import annotations

import uuid
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
from app.retrieval.ports import RetrievedContextItem
from app.memory.ports import MemoryProvider


class NutritionToolAdapter(Protocol):
    """The graph's complete nutrition authority; it never receives a Repository."""

    def search_food_catalog(self, request: FoodSearchInput) -> FoodSearchResult: ...

    def calculate_nutrition(
        self, request: NutritionCalculationInput
    ) -> NutritionCalculationResult: ...

    def validate_nutrition_result(
        self, request: NutritionValidationInput
    ) -> NutritionValidationResult: ...

    def retrieve_personal_context(
        self, *, user_id: uuid.UUID, query: str, catalog_version: str | None = None
    ) -> list[RetrievedContextItem]: ...


class NutritionServiceToolAdapter:
    """Adapter keeps graph imports stable if the nutrition implementation evolves."""

    def __init__(self, *, service: NutritionService, context_service: object | None = None) -> None:
        self._service = service
        self._context_service = context_service

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

    def retrieve_personal_context(self, *, user_id: uuid.UUID, query: str, catalog_version: str | None = None) -> list[RetrievedContextItem]:
        if self._context_service is None:
            return []
        return self._context_service.retrieve(user_id=user_id, query=query, catalog_version=catalog_version)  # type: ignore[union-attr,arg-type]


class SessionNutritionToolAdapter:
    """Build a short-lived read session per deterministic tool invocation.

    A graph still receives only the narrow tool port; SQLAlchemy remains encapsulated in this
    infrastructure adapter and never leaks into graph nodes.
    """

    def __init__(self, *, session_factory: Callable[[], Session], memory_provider: MemoryProvider | None = None) -> None:
        self._session_factory = session_factory
        self._memory_provider = memory_provider

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

    def retrieve_personal_context(self, *, user_id: uuid.UUID, query: str, catalog_version: str | None = None) -> list[RetrievedContextItem]:
        from app.memory.providers import FakeMemoryProvider
        from app.memory.repository import SqlAlchemyMemoryLedgerRepository
        from app.memory.service import MemoryService
        from app.retrieval.repository import SqlAlchemyRetrievalRepository
        from app.retrieval.service import PersonalContextService

        session = self._session_factory()
        try:
            memory_service = MemoryService(
                repository=SqlAlchemyMemoryLedgerRepository(session),
                provider=self._memory_provider if self._memory_provider is not None else FakeMemoryProvider(),
            )
            return PersonalContextService(memory_service=memory_service, repository=SqlAlchemyRetrievalRepository(session)).retrieve(user_id=user_id, query=query, catalog_version=catalog_version)
        finally:
            session.close()
