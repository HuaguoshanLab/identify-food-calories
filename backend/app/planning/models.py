"""Minimal, owner-bound persisted inputs for deterministic diet planning."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.auth.models import Base


class PlanningProfile(Base):
    """One active snapshot per user; preferences remain exclusively in the memory ledger."""

    __tablename__ = "planning_profiles"
    __table_args__ = (
        CheckConstraint("height_cm >= 100 AND height_cm <= 250", name="ck_planning_profiles_height_range"),
        CheckConstraint("weight_kg >= 20 AND weight_kg <= 350", name="ck_planning_profiles_weight_range"),
        CheckConstraint("age_years >= 1 AND age_years <= 130", name="ck_planning_profiles_age_range"),
        CheckConstraint("formula_variant IN ('mifflin_st_jeor_male', 'mifflin_st_jeor_female')", name="ck_planning_profiles_formula_variant"),
        CheckConstraint("activity_level IN ('sedentary', 'light', 'moderate', 'high', 'very_high')", name="ck_planning_profiles_activity_level"),
        CheckConstraint("goal IN ('maintain', 'loss', 'gain')", name="ck_planning_profiles_goal"),
        CheckConstraint("goal_speed IN ('maintain', 'gradual_loss', 'gradual_gain')", name="ck_planning_profiles_goal_speed"),
        UniqueConstraint("user_id", "id", name="uq_planning_profiles_user_id"),
        Index("uq_planning_profiles_active_user", "user_id", unique=True, postgresql_where=text("deleted_at IS NULL")),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    height_cm: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    age_years: Mapped[int] = mapped_column(Integer, nullable=False)
    formula_variant: Mapped[str] = mapped_column(String(48), nullable=False)
    activity_level: Mapped[str] = mapped_column(String(24), nullable=False)
    goal: Mapped[str] = mapped_column(String(16), nullable=False)
    goal_speed: Mapped[str] = mapped_column(String(24), nullable=False)
    target_policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    formula_version: Mapped[str] = mapped_column(String(80), nullable=False)
    # A completed-plan projection pins this value; every profile mutation revokes that fact.
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PlanningCompletionProjection(Base):
    """Auditable fact that one validated planning run may authorize dashboard targets."""

    __tablename__ = "planning_completion_projections"
    __table_args__ = (
        CheckConstraint("profile_revision >= 1", name="ck_planning_completion_projections_profile_revision"),
        CheckConstraint("target_version = btrim(target_version) AND target_version <> ''", name="ck_planning_completion_projections_target_version"),
        CheckConstraint(
            "energy_kcal_lower >= 0 AND energy_kcal_upper >= energy_kcal_lower "
            "AND carbohydrate_g_lower >= 0 AND carbohydrate_g_upper >= carbohydrate_g_lower "
            "AND protein_g_lower >= 0 AND protein_g_upper >= protein_g_lower "
            "AND fat_g_lower >= 0 AND fat_g_upper >= fat_g_lower",
            name="ck_planning_completion_projections_target_ranges",
        ),
        CheckConstraint(
            "(revoked_at IS NULL AND revocation_reason IS NULL) OR "
            "(revoked_at IS NOT NULL AND revocation_reason IN ('profile_revision_changed', 'profile_deleted'))",
            name="ck_planning_completion_projections_revocation",
        ),
        UniqueConstraint("user_id", "completed_run_id", name="uq_planning_completion_projections_user_run"),
        ForeignKeyConstraint(
            ["user_id", "profile_id"], ["planning_profiles.user_id", "planning_profiles.id"],
            name="fk_planning_completion_projections_profile", ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["user_id", "completed_thread_id"], ["agent_threads.user_id", "agent_threads.id"],
            name="fk_planning_completion_projections_thread", ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["user_id", "completed_thread_id", "completed_run_id"],
            ["agent_runs.user_id", "agent_runs.thread_id", "agent_runs.id"],
            name="fk_planning_completion_projections_run", ondelete="RESTRICT",
        ),
        Index(
            "ix_planning_completion_projections_user_active",
            "user_id",
            "completed_at",
            "id",
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    profile_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    completed_thread_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    completed_run_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    profile_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    target_version: Mapped[str] = mapped_column(String(80), nullable=False)
    energy_kcal_lower: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    energy_kcal_upper: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    carbohydrate_g_lower: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    carbohydrate_g_upper: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    protein_g_lower: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    protein_g_upper: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    fat_g_lower: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    fat_g_upper: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revocation_reason: Mapped[str | None] = mapped_column(String(48))


class ControlledRecipe(Base):
    """Server-side R-03 evidence; recipe ingredients hold references, never nutrient totals."""

    __tablename__ = "controlled_recipes"
    __table_args__ = (
        CheckConstraint("stable_id = btrim(stable_id) AND stable_id <> ''", name="ck_controlled_recipes_stable_id"),
        CheckConstraint("display_name = btrim(display_name) AND display_name <> ''", name="ck_controlled_recipes_display_name"),
        CheckConstraint("recipe_version = btrim(recipe_version) AND recipe_version <> ''", name="ck_controlled_recipes_recipe_version"),
        CheckConstraint("catalog_version = btrim(catalog_version) AND catalog_version <> ''", name="ck_controlled_recipes_catalog_version"),
        CheckConstraint("meal_slot IN ('breakfast', 'lunch', 'dinner')", name="ck_controlled_recipes_meal_slot"),
        CheckConstraint("portion_description = btrim(portion_description) AND portion_description <> ''", name="ck_controlled_recipes_portion_description"),
        CheckConstraint("portion_grams > 0", name="ck_controlled_recipes_portion_grams_positive"),
        CheckConstraint("method_tags = btrim(method_tags) AND method_tags <> ''", name="ck_controlled_recipes_method_tags"),
        CheckConstraint("flavour_tags = btrim(flavour_tags) AND flavour_tags <> ''", name="ck_controlled_recipes_flavour_tags"),
        CheckConstraint("source_kind = 'project_authored'", name="ck_controlled_recipes_project_authored"),
        CheckConstraint("source_reference = btrim(source_reference) AND source_reference <> ''", name="ck_controlled_recipes_source_reference"),
        CheckConstraint("license_name = 'LicenseRef-Project-Authored-v1'", name="ck_controlled_recipes_license"),
        CheckConstraint("audit_status = 'approved'", name="ck_controlled_recipes_audit_status"),
        CheckConstraint("audited_by_role = 'nutrition_catalog_reviewer'", name="ck_controlled_recipes_auditor_role"),
        CheckConstraint("audit_version = btrim(audit_version) AND audit_version <> ''", name="ck_controlled_recipes_audit_version"),
        UniqueConstraint("stable_id", "recipe_version", name="uq_controlled_recipes_stable_version"),
        Index("ix_controlled_recipes_active_catalog_slot", "catalog_version_id", "meal_slot", postgresql_where=text("is_active")),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    stable_id: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    recipe_version: Mapped[str] = mapped_column(String(80), nullable=False)
    catalog_version_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("nutrition_catalog_versions.id", ondelete="RESTRICT"), nullable=False)
    catalog_version: Mapped[str] = mapped_column(String(80), nullable=False)
    meal_slot: Mapped[str] = mapped_column(String(16), nullable=False)
    portion_description: Mapped[str] = mapped_column(String(120), nullable=False)
    portion_grams: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    method_tags: Mapped[str] = mapped_column(Text, nullable=False)
    flavour_tags: Mapped[str] = mapped_column(Text, nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="project_authored")
    source_reference: Mapped[str] = mapped_column(Text, nullable=False)
    license_name: Mapped[str] = mapped_column(String(80), nullable=False, default="LicenseRef-Project-Authored-v1")
    audit_status: Mapped[str] = mapped_column(String(24), nullable=False, default="approved")
    audited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    audited_by_role: Mapped[str] = mapped_column(String(48), nullable=False, default="nutrition_catalog_reviewer")
    audit_version: Mapped[str] = mapped_column(String(80), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    ingredients: Mapped[list["ControlledRecipeIngredient"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan"
    )


class ControlledRecipeIngredient(Base):
    """One ordered, fixed-gram link to a qualified nutrition catalog item."""

    __tablename__ = "controlled_recipe_ingredients"
    __table_args__ = (
        CheckConstraint("position >= 0", name="ck_controlled_recipe_ingredients_position"),
        CheckConstraint("catalog_version = btrim(catalog_version) AND catalog_version <> ''", name="ck_controlled_recipe_ingredients_catalog_version"),
        CheckConstraint("portion_description = btrim(portion_description) AND portion_description <> ''", name="ck_controlled_recipe_ingredients_portion_description"),
        CheckConstraint("grams > 0", name="ck_controlled_recipe_ingredients_grams_positive"),
        UniqueConstraint("recipe_id", "position", name="uq_controlled_recipe_ingredients_position"),
        Index("ix_controlled_recipe_ingredients_recipe", "recipe_id", "position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    recipe_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("controlled_recipes.id", ondelete="CASCADE"), nullable=False)
    food_catalog_item_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("food_catalog_items.id", ondelete="RESTRICT"), nullable=False)
    catalog_version: Mapped[str] = mapped_column(String(80), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    grams: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    portion_description: Mapped[str] = mapped_column(String(120), nullable=False)

    recipe: Mapped[ControlledRecipe] = relationship(back_populates="ingredients")
