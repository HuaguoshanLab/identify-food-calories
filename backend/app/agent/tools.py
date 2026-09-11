"""Tool adapter boundary between graph orchestration and deterministic nutrition services."""

from __future__ import annotations

import uuid
import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, cast
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
from app.core.tracing import DisabledTracingRuntime, TracingRuntime
from app.providers.embedding.ports import EmbeddingProvider
from app.retrieval.ports import RetrievedContextItem
from app.memory.ports import MemoryProvider
from app.planning.schemas import (
    CONTROLLED_RECIPE_VERSION,
    DailyTarget,
    MealCompositionResult,
    PlanValidationAction,
    PlanValidationResult,
    PlanningProfileInput,
    PreferenceReview,
    MealSlot,
    PlannedMeal,
    TargetCalculationResult,
)
from app.planning.schemas import PlanningProfileWrite


@dataclass(frozen=True, slots=True)
class CapturedPreferenceSummary:
    """Safe direct-write result available to graph code without storage identifiers."""

    category: Literal["goal", "avoidance", "stable_preference"]
    canonical_text: str


class NutritionToolAdapter(Protocol):
    """The graph's complete nutrition authority; it never receives a Repository."""

    async def search_food_catalog(self, request: FoodSearchInput) -> FoodSearchResult: ...

    def calculate_nutrition(
        self, request: NutritionCalculationInput
    ) -> NutritionCalculationResult: ...

    def validate_nutrition_result(
        self, request: NutritionValidationInput
    ) -> NutritionValidationResult: ...

    def retrieve_personal_context(
        self, *, user_id: uuid.UUID, query: str, catalog_version: str | None = None
    ) -> list[RetrievedContextItem]: ...

    def capture_explicit_preferences(
        self, *, user_id: uuid.UUID, run_id: uuid.UUID, statement: str
    ) -> tuple[CapturedPreferenceSummary, ...]: ...


class PlanningToolAdapter(Protocol):
    """The planning graph's complete authority; it never receives a Session or repository."""

    async def search_food_catalog(self, request: FoodSearchInput) -> FoodSearchResult: ...

    def calculate_daily_target(
        self, *, profile: PlanningProfileInput, preferences: PreferenceReview
    ) -> TargetCalculationResult: ...

    def compose_daily_plan(
        self, *, user_id: uuid.UUID, target: DailyTarget, preferences: PreferenceReview, replan_count: int
    ) -> MealCompositionResult: ...

    def validate_daily_plan(
        self, *, target: DailyTarget, meals: tuple[PlannedMeal, ...], replan_count: int
    ) -> PlanValidationResult: ...

    def upsert_planning_profile(
        self, *, user_id: uuid.UUID, profile: PlanningProfileInput, command_key: str
    ) -> None: ...

    def capture_explicit_preferences(
        self, *, user_id: uuid.UUID, run_id: uuid.UUID, statement: str
    ) -> tuple[CapturedPreferenceSummary, ...]: ...

    def replace_planning_slot(
        self,
        *,
        user_id: uuid.UUID,
        target: DailyTarget,
        preferences: PreferenceReview,
        existing_meals: tuple[PlannedMeal, ...],
        affected_slot: MealSlot,
        feedback_intent: str,
        replan_count: int,
    ) -> MealCompositionResult: ...


class NutritionServiceToolAdapter:
    """Adapter keeps graph imports stable if the nutrition implementation evolves."""

    def __init__(
        self,
        *,
        service: NutritionService,
        context_service: object | None = None,
        explicit_preference_capture_service: object | None = None,
    ) -> None:
        self._service = service
        self._context_service = context_service
        self._explicit_preference_capture_service = explicit_preference_capture_service

    async def search_food_catalog(self, request: FoodSearchInput) -> FoodSearchResult:
        return await self._service.search_food_catalog(request)

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
        return self._context_service.retrieve(user_id=user_id, query=query, catalog_version=catalog_version)  # type: ignore[union-attr,attr-defined,arg-type]

    def capture_explicit_preferences(
        self, *, user_id: uuid.UUID, run_id: uuid.UUID, statement: str
    ) -> tuple[CapturedPreferenceSummary, ...]:
        if self._explicit_preference_capture_service is None:
            return ()
        captured = self._explicit_preference_capture_service.capture_explicit_preferences(  # type: ignore[union-attr,attr-defined]
            user_id=user_id, run_id=run_id, statement=statement
        )
        return tuple(
            CapturedPreferenceSummary(category=ledger.category, canonical_text=ledger.canonical_text)
            for ledger in captured
        )


class SessionNutritionToolAdapter:
    """Build a short-lived read session per deterministic tool invocation.

    A graph still receives only the narrow tool port; SQLAlchemy remains encapsulated in this
    infrastructure adapter and never leaks into graph nodes.
    """

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        memory_provider: MemoryProvider | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        tracing: TracingRuntime | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._memory_provider = memory_provider
        self._embedding_provider = embedding_provider
        self._tracing = tracing or DisabledTracingRuntime()

    def _service(self) -> tuple[Session, NutritionService]:
        from app.nutrition.repository import SqlAlchemyNutritionRepository
        from app.nutrition.search_repository import SqlAlchemyHybridFoodSearchRepository

        session = self._session_factory()
        repository = SqlAlchemyNutritionRepository(session)
        return session, NutritionService(
            repository=repository,
            search_repository=SqlAlchemyHybridFoodSearchRepository(session),
            embedding_provider=self._embedding_provider,
            tracing=self._tracing,
        )

    async def search_food_catalog(self, request: FoodSearchInput) -> FoodSearchResult:
        return await asyncio.to_thread(self._search_food_catalog_in_thread, request)

    def _search_food_catalog_in_thread(self, request: FoodSearchInput) -> FoodSearchResult:
        """Keep one synchronous Session confined to the worker thread that consumes it.

        The service owns an async embedding call, so the worker owns a short-lived event loop
        rather than leaking its Session back to the graph event loop.
        """

        session, service = self._service()
        try:
            with asyncio.Runner() as runner:
                return runner.run(service.search_food_catalog(request))
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

    def capture_explicit_preferences(
        self, *, user_id: uuid.UUID, run_id: uuid.UUID, statement: str
    ) -> tuple[CapturedPreferenceSummary, ...]:
        from app.memory.providers import FakeMemoryProvider
        from app.memory.repository import SqlAlchemyMemoryLedgerRepository
        from app.memory.service import MemoryService

        session = self._session_factory()
        try:
            captured = MemoryService(
                repository=SqlAlchemyMemoryLedgerRepository(session),
                provider=self._memory_provider if self._memory_provider is not None else FakeMemoryProvider(),
                commit=session.commit,
                rollback=session.rollback,
            ).capture_explicit_preferences(user_id=user_id, source_run_id=run_id, statement=statement)
            return tuple(
                CapturedPreferenceSummary(category=cast(Literal["goal", "avoidance", "stable_preference"], ledger.category), canonical_text=ledger.canonical_text)
                for ledger in captured
            )
        finally:
            session.close()

    def _planning_service(self):
        """Create deterministic planning services behind the same narrow runtime adapter."""

        from app.nutrition.repository import SqlAlchemyNutritionRepository
        from app.nutrition.service import NutritionService
        from app.planning.repository import SqlAlchemyPlanningProfileRepository
        from app.planning.service import PlanningService

        session = self._session_factory()
        repository = SqlAlchemyPlanningProfileRepository(session)
        return session, PlanningService(
            repository=repository,
            nutrition_port=NutritionService(
                repository=SqlAlchemyNutritionRepository(session),
                tracing=self._tracing,
            ),
        )

    def calculate_daily_target(
        self, *, profile: PlanningProfileInput, preferences: PreferenceReview
    ) -> TargetCalculationResult:
        session, service = self._planning_service()
        try:
            return service.calculate_daily_target(profile, preferences)
        finally:
            session.close()

    def compose_daily_plan(
        self, *, user_id: uuid.UUID, target: DailyTarget, preferences: PreferenceReview, replan_count: int
    ) -> MealCompositionResult:
        # Managed candidates carry their catalog version.  Do not pin the planner to a seed
        # catalog, or newly imported admin candidates can never enter a meal plan.
        session, service = self._planning_service()
        try:
            return service.compose_daily_meals(
                user_id=user_id,
                catalog_version=None,
                preferences=preferences,
                recipe_version=CONTROLLED_RECIPE_VERSION,
            )
        finally:
            session.close()

    def replace_planning_slot(
        self,
        *,
        user_id: uuid.UUID,
        target: DailyTarget,
        preferences: PreferenceReview,
        existing_meals: tuple[PlannedMeal, ...],
        affected_slot: MealSlot,
        feedback_intent: str,
        replan_count: int,
    ) -> MealCompositionResult:
        # PlanningService owns candidate eligibility; this adapter only preserves untouched slots.
        session, service = self._planning_service()
        try:
            current = next((meal for meal in existing_meals if meal.slot is affected_slot), None)
            if current is None:
                return MealCompositionResult(action=PlanValidationAction.NEEDS_INPUT, safe_message="请选择早餐、午餐或晚餐。")
            replacement_plan = service.compose_daily_meals(
                user_id=user_id,
                catalog_version=None,
                preferences=preferences,
                recipe_version=CONTROLLED_RECIPE_VERSION,
                exclude_recipe_ids=(current.recipe_id,),
            )
            if replacement_plan.action is not PlanValidationAction.PASS:
                return replacement_plan
            replacement = next(meal for meal in replacement_plan.meals if meal.slot is affected_slot)
            return MealCompositionResult(
                action=PlanValidationAction.PASS,
                meals=tuple(replacement if meal.slot is affected_slot else meal for meal in existing_meals),
                safe_message="已替换指定餐次并保留其余餐次。",
            )
        finally:
            session.close()

    def validate_daily_plan(
        self, *, target: DailyTarget, meals: tuple[PlannedMeal, ...], replan_count: int
    ) -> PlanValidationResult:
        session, service = self._planning_service()
        try:
            return service.validate_plan(
                target=target,
                meals=meals,
                allow_target_relaxation=replan_count >= 2,
            )
        finally:
            session.close()

    def upsert_planning_profile(
        self, *, user_id: uuid.UUID, profile: PlanningProfileInput, command_key: str
    ) -> None:
        """Persist only the explicitly approved minimal profile through its domain service."""

        from app.planning.repository import SqlAlchemyPlanningProfileRepository
        from app.planning.service import PlanningProfileService

        session = self._session_factory()
        try:
            payload = PlanningProfileWrite.model_validate(
                profile.model_dump(
                    exclude={
                        "is_pregnant_or_breastfeeding",
                        "has_disease_or_treatment",
                        "uses_medication",
                        "has_eating_disorder_or_self_harm_risk",
                        "has_extreme_weight_control_goal",
                    }
                )
            )
            PlanningProfileService(
                repository=SqlAlchemyPlanningProfileRepository(session),
                commit=session.commit,
                rollback=session.rollback,
            ).replace_profile(user_id=user_id, payload=payload)
        finally:
            session.close()
