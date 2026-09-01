"""Tenant-filtered SQLAlchemy adapter for the minimal planning profile authority."""

from __future__ import annotations

import uuid

from sqlalchemy import Select, exists, or_, select
from sqlalchemy.orm import Session, selectinload

from app.nutrition.models import FoodCatalogItem, NutritionCatalogVersion
from app.planning.models import (
    ControlledRecipe as ControlledRecipeModel,
    ControlledRecipeIngredient as ControlledRecipeIngredientModel,
    PlanningProfile,
)
from app.planning.schemas import (
    ActivityLevel,
    ControlledRecipe,
    ControlledRecipeIngredient,
    FormulaVariant,
    MealSlot,
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

    def list_controlled_recipes(self, *, catalog_version: str) -> list[ControlledRecipe]:
        """Expose only recipes whose complete ingredient chain remains qualified and aligned."""

        rows = self._session.scalars(
            self._active_recipe_statement(catalog_version=catalog_version)
        ).unique()
        return [self._to_controlled_recipe(row) for row in rows]

    @staticmethod
    def _profile_statement(*, user_id: uuid.UUID):
        return select(PlanningProfile).where(
            PlanningProfile.user_id == user_id, PlanningProfile.deleted_at.is_(None)
        )

    @staticmethod
    def _active_recipe_statement(*, catalog_version: str) -> Select[tuple[ControlledRecipeModel]]:
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
                ControlledRecipeModel.catalog_version == catalog_version,
                NutritionCatalogVersion.version == catalog_version,
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
