"""Tenant-filtered SQLAlchemy adapter for the minimal planning profile authority."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Select, and_, exists, or_, select
from sqlalchemy.orm import Session, aliased, selectinload

from app.agent.models import AgentRun, AgentThread
from app.dashboard.ports import PlanningTargetEligibility
from app.nutrition.models import FoodCatalogItem, NutritionCatalogVersion
from app.admin.models import CatalogActivePublication, CatalogPublication, CatalogPublicationEligibility
from app.planning.models import (
    ControlledRecipe as ControlledRecipeModel,
    ControlledRecipeIngredient as ControlledRecipeIngredientModel,
    ManagedRecipeCandidate as ManagedRecipeCandidateModel,
    DietPlanVersion,
    PlanningCompletionProjection,
    PlanningProfile,
)
from app.planning.schemas import (
    ActivityLevel,
    ControlledRecipe,
    ControlledRecipeIngredient,
    FormulaVariant,
    MealSlot,
    ManagedRecipeCandidate,
    ManagedRecipeCandidateStatus,
    PlanningGoal,
    PlanningProfileInput,
)


class SqlAlchemyPlanningProfileRepository:
    """Ownership is proved in SQL so profile IDs never become an existence oracle."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_profile_for_user(self, *, user_id: uuid.UUID, for_update: bool = False) -> PlanningProfile | None:
        statement = self._profile_statement(user_id=user_id)
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def get_planning_profile(self, *, user_id: uuid.UUID) -> PlanningProfileInput | None:
        profile = self.get_profile_for_user(user_id=user_id)
        if profile is None:
            return None
        return PlanningProfileInput(
            height_cm=profile.height_cm, weight_kg=profile.weight_kg, age_years=profile.age_years,
            formula_variant=FormulaVariant(profile.formula_variant),
            activity_level=ActivityLevel(profile.activity_level),
            goal=PlanningGoal(profile.goal), goal_speed=profile.goal_speed,
        )

    def add_profile(self, profile: PlanningProfile) -> PlanningProfile:
        self._session.add(profile)
        self._session.flush()
        return profile

    def add_completion_projection(
        self, projection: PlanningCompletionProjection
    ) -> PlanningCompletionProjection:
        self._session.add(projection)
        self._session.flush()
        return projection

    def get_completion_projection_for_run_for_user(
        self, *, user_id: uuid.UUID, run_id: uuid.UUID, for_update: bool = False
    ) -> PlanningCompletionProjection | None:
        statement = select(PlanningCompletionProjection).where(
            PlanningCompletionProjection.user_id == user_id,
            PlanningCompletionProjection.completed_run_id == run_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def get_completion_projection_for_user(
        self, *, user_id: uuid.UUID, for_update: bool = False
    ) -> PlanningCompletionProjection | None:
        statement = select(PlanningCompletionProjection).where(
            PlanningCompletionProjection.user_id == user_id,
            PlanningCompletionProjection.revoked_at.is_(None),
        ).order_by(PlanningCompletionProjection.completed_at.desc(), PlanningCompletionProjection.id.desc())
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def revoke_completion_projection_for_user(
        self, *, user_id: uuid.UUID, reason: str, revoked_at: datetime
    ) -> bool:
        projection = self.get_completion_projection_for_user(user_id=user_id, for_update=True)
        if projection is None:
            return False
        projection.revoked_at = revoked_at
        projection.revocation_reason = reason
        self._session.flush()
        return True

    def get_dashboard_target_eligibility(self, *, user_id: uuid.UUID) -> PlanningTargetEligibility:
        projection = self._session.scalar(
            select(PlanningCompletionProjection)
            .join(
                PlanningProfile,
                and_(
                    PlanningProfile.id == PlanningCompletionProjection.profile_id,
                    PlanningProfile.user_id == PlanningCompletionProjection.user_id,
                ),
            )
            .join(
                AgentThread,
                and_(
                    AgentThread.id == PlanningCompletionProjection.completed_thread_id,
                    AgentThread.user_id == PlanningCompletionProjection.user_id,
                ),
            )
            .join(
                AgentRun,
                and_(
                    AgentRun.id == PlanningCompletionProjection.completed_run_id,
                    AgentRun.thread_id == PlanningCompletionProjection.completed_thread_id,
                    AgentRun.user_id == PlanningCompletionProjection.user_id,
                ),
            )
            .where(
                PlanningCompletionProjection.user_id == user_id,
                PlanningCompletionProjection.revoked_at.is_(None),
                PlanningProfile.deleted_at.is_(None),
                PlanningProfile.revision == PlanningCompletionProjection.profile_revision,
                AgentRun.status == "completed",
            )
            .order_by(PlanningCompletionProjection.completed_at.desc(), PlanningCompletionProjection.id.desc())
        )
        return PlanningTargetEligibility.unavailable() if projection is None else PlanningTargetEligibility.from_projection(projection)

    def list_controlled_recipes(
        self, *, catalog_version: str | None, recipe_version: str,
        meal_slot: MealSlot | None = None, after_id: uuid.UUID | None = None,
        limit: int | None = None,
    ) -> list[ControlledRecipe]:
        """Expose only recipes whose complete ingredient chain remains qualified and aligned."""

        statement = self._active_recipe_statement(
            catalog_version=catalog_version, recipe_version=recipe_version
        )
        if meal_slot is not None:
            statement = statement.where(ControlledRecipeModel.meal_slot == meal_slot.value)
        if after_id is not None:
            statement = statement.where(ControlledRecipeModel.id > after_id)
        if limit is not None:
            statement = statement.order_by(None).order_by(ControlledRecipeModel.id).limit(limit)
        rows = self._session.scalars(statement).unique()
        return [self._to_controlled_recipe(row) for row in rows]

    def has_managed_recipe_candidates(self) -> bool:
        # Disabled/deleted rows still prove that administrators adopted this pool.
        # Its deliberate empty state must not silently reactivate the bootstrap recipes.
        return bool(self._session.scalar(select(exists().where(ManagedRecipeCandidateModel.id.is_not(None)))))

    def list_managed_recipe_candidates(
        self, *, catalog_version: str | None,
        meal_slot: MealSlot | None = None, after_id: uuid.UUID | None = None,
        limit: int | None = None, food_ids: tuple[uuid.UUID, ...] | None = None,
        recipe_id: uuid.UUID | None = None, recipe_revision: int | None = None,
    ) -> list[ManagedRecipeCandidate]:
        """Return only candidates whose referenced catalog row remains calculable now."""

        imported_statement = (
            select(ManagedRecipeCandidateModel)
            .join(FoodCatalogItem, FoodCatalogItem.id == ManagedRecipeCandidateModel.food_catalog_item_id)
            .join(NutritionCatalogVersion, NutritionCatalogVersion.id == FoodCatalogItem.catalog_version_id)
            .where(
                ManagedRecipeCandidateModel.status == "enabled",
                ManagedRecipeCandidateModel.deleted_at.is_(None),
                FoodCatalogItem.is_qualified.is_(True),
                FoodCatalogItem.energy_kcal_per_100g.is_not(None),
                FoodCatalogItem.protein_g_per_100g.is_not(None),
                FoodCatalogItem.fat_g_per_100g.is_not(None),
                FoodCatalogItem.carbohydrate_g_per_100g.is_not(None),
            )
        )
        if catalog_version is not None:
            imported_statement = imported_statement.where(NutritionCatalogVersion.version == catalog_version)
        latest = aliased(CatalogPublicationEligibility)
        latest_eligibility = (
            select(latest.id)
            .where(latest.publication_id == CatalogPublication.id)
            .order_by(
                latest.occurred_at.desc(),
                latest.id.desc(),
            )
            .limit(1)
            .scalar_subquery()
        )
        publication_statement = (
            select(ManagedRecipeCandidateModel)
            .join(
                CatalogPublication,
                CatalogPublication.id == ManagedRecipeCandidateModel.catalog_publication_id,
            )
            .join(
                CatalogActivePublication,
                CatalogActivePublication.publication_id == CatalogPublication.id,
            )
            .join(
                CatalogPublicationEligibility,
                CatalogPublicationEligibility.id == latest_eligibility,
            )
            .where(
                ManagedRecipeCandidateModel.status == "enabled",
                ManagedRecipeCandidateModel.deleted_at.is_(None),
                CatalogPublicationEligibility.status == "eligible",
            )
        )
        if catalog_version is not None:
            publication_statement = publication_statement.where(
                ManagedRecipeCandidateModel.nutrition_catalog_version == catalog_version
            )
        filters = []
        if meal_slot is not None:
            filters.append(ManagedRecipeCandidateModel.meal_slot == meal_slot.value)
        if after_id is not None:
            filters.append(ManagedRecipeCandidateModel.id > after_id)
        if food_ids is not None:
            filters.append(or_(
                ManagedRecipeCandidateModel.food_catalog_item_id.in_(food_ids),
                ManagedRecipeCandidateModel.catalog_publication_id.in_(food_ids),
            ))
        if recipe_id is not None:
            filters.append(ManagedRecipeCandidateModel.id == recipe_id)
        if recipe_revision is not None:
            filters.append(ManagedRecipeCandidateModel.revision == recipe_revision)
        branches = []
        for source in (imported_statement, publication_statement):
            source = source.with_only_columns(ManagedRecipeCandidateModel.id).where(*filters)
            if limit is not None:
                source = source.order_by(ManagedRecipeCandidateModel.id).limit(limit)
            branches.append(select(source.subquery().c.id))
        # Each source supplies at most one page before merging, so UNION does
        # not materialize the whole qualified catalog on every page request.
        qualified_ids = branches[0].union(branches[1])
        statement = select(ManagedRecipeCandidateModel).where(ManagedRecipeCandidateModel.id.in_(qualified_ids))
        if limit is not None:
            statement = statement.order_by(ManagedRecipeCandidateModel.id).limit(limit)
        else:
            statement = statement.order_by(ManagedRecipeCandidateModel.meal_slot, ManagedRecipeCandidateModel.updated_at, ManagedRecipeCandidateModel.id)
        rows = self._session.scalars(statement)
        return [
            ManagedRecipeCandidate(
                id=candidate.id,
                nutrition_item_id=(
                    candidate.food_catalog_item_id
                    if candidate.food_catalog_item_id is not None
                    else candidate.catalog_publication_id
                ),
                catalog_version=candidate.nutrition_catalog_version,
                display_name=candidate.catalog_food_name,
                meal_slot=MealSlot(candidate.meal_slot),
                portion_grams=candidate.portion_grams,
                portion_description=candidate.portion_description,
                method_tags=tuple(tag for tag in candidate.method_tags.split("|") if tag),
                flavour_tags=tuple(tag for tag in candidate.flavour_tags.split("|") if tag),
                status=ManagedRecipeCandidateStatus(candidate.status),
                revision=candidate.revision,
            )
            for candidate in rows
        ]

    def list_recent_recipe_ids(
        self, *, user_id: uuid.UUID, plan_limit: int
    ) -> tuple[uuid.UUID, ...]:
        """Read only archived recipe provenance; mutable candidate rows are never history truth."""

        snapshots = self._session.scalars(
            select(DietPlanVersion.provenance)
            .where(
                DietPlanVersion.user_id == user_id,
                DietPlanVersion.report.is_not(None),
                DietPlanVersion.provenance.is_not(None),
            )
            .order_by(DietPlanVersion.created_at.desc(), DietPlanVersion.id.desc())
            .limit(plan_limit)
        )
        ids: list[uuid.UUID] = []
        for provenance in snapshots:
            if not isinstance(provenance, dict):
                continue
            recipes = provenance.get("recipes")
            if not isinstance(recipes, list):
                continue
            for recipe in recipes:
                if not isinstance(recipe, dict) or not isinstance(recipe.get("recipe_id"), str):
                    continue
                try:
                    recipe_id = uuid.UUID(recipe["recipe_id"])
                except ValueError:
                    continue
                if recipe_id not in ids:
                    ids.append(recipe_id)
        return tuple(ids)

    @staticmethod
    def _profile_statement(*, user_id: uuid.UUID):
        return select(PlanningProfile).where(
            PlanningProfile.user_id == user_id, PlanningProfile.deleted_at.is_(None)
        )

    @staticmethod
    def _active_recipe_statement(
        *, catalog_version: str | None, recipe_version: str
    ) -> Select[tuple[ControlledRecipeModel]]:
        disqualified_active_publication = (
            select(CatalogPublicationEligibility.id)
            .join(CatalogPublication, CatalogPublication.id == CatalogPublicationEligibility.publication_id)
            .join(CatalogActivePublication, CatalogActivePublication.publication_id == CatalogPublication.id)
            .where(
                CatalogPublicationEligibility.status == "disqualified",
                CatalogPublication.snapshot["canonical_name"].as_string() == FoodCatalogItem.canonical_name,
            )
        )
        invalid_ingredient = (
            select(ControlledRecipeIngredientModel.id)
            .join(
                FoodCatalogItem,
                FoodCatalogItem.id == ControlledRecipeIngredientModel.food_catalog_item_id,
            )
            .where(
                ControlledRecipeIngredientModel.recipe_id == ControlledRecipeModel.id,
                or_(
                    ControlledRecipeIngredientModel.catalog_version
                    != ControlledRecipeModel.catalog_version,
                    FoodCatalogItem.catalog_version_id
                    != ControlledRecipeModel.catalog_version_id,
                    FoodCatalogItem.is_qualified.is_not(True),
                    FoodCatalogItem.energy_kcal_per_100g.is_(None),
                    FoodCatalogItem.protein_g_per_100g.is_(None),
                    FoodCatalogItem.fat_g_per_100g.is_(None),
                    FoodCatalogItem.carbohydrate_g_per_100g.is_(None),
                    disqualified_active_publication.exists(),
                ),
            )
        )
        return (
            select(ControlledRecipeModel)
            .options(selectinload(ControlledRecipeModel.ingredients))
            .join(
                NutritionCatalogVersion,
                NutritionCatalogVersion.id == ControlledRecipeModel.catalog_version_id,
            )
            .where(
                ControlledRecipeModel.is_active.is_(True),
                ControlledRecipeModel.source_kind == "project_authored",
                ControlledRecipeModel.license_name == "LicenseRef-Project-Authored-v1",
                ControlledRecipeModel.audit_status == "approved",
                ControlledRecipeModel.audited_by_role == "nutrition_catalog_reviewer",
                or_(catalog_version is None, ControlledRecipeModel.catalog_version == catalog_version),
                ControlledRecipeModel.recipe_version == recipe_version,
                NutritionCatalogVersion.version == ControlledRecipeModel.catalog_version,
                ~exists(invalid_ingredient),
            )
            .order_by(ControlledRecipeModel.meal_slot, ControlledRecipeModel.display_name)
        )

    @staticmethod
    def _to_controlled_recipe(row: ControlledRecipeModel) -> ControlledRecipe:
        return ControlledRecipe(
            id=row.id,
            stable_id=row.stable_id,
            display_name=row.display_name,
            recipe_version=row.recipe_version,
            catalog_version=row.catalog_version,
            meal_slots=(MealSlot(row.meal_slot),),
            portion_description=row.portion_description,
            portion_grams=row.portion_grams,
            method_tags=tuple(tag for tag in row.method_tags.split("|") if tag),
            flavour_tags=tuple(tag for tag in row.flavour_tags.split("|") if tag),
            ingredients=tuple(
                ControlledRecipeIngredient(
                    food_id=ingredient.food_catalog_item_id,
                    catalog_version=ingredient.catalog_version,
                    grams=ingredient.grams,
                    portion_description=ingredient.portion_description,
                )
                for ingredient in sorted(row.ingredients, key=lambda item: item.position)
            ),
            source_kind=row.source_kind,
            source_reference=row.source_reference,
            license_name=row.license_name,
            audit_status=row.audit_status,
            audited_at=row.audited_at,
            audited_by_role=row.audited_by_role,
            audit_version=row.audit_version,
            is_active=row.is_active,
        )
