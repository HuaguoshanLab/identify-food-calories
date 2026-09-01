"""Create auditable controlled recipe and fixed-ingredient schema.

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "controlled_recipes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("stable_id", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("recipe_version", sa.String(length=80), nullable=False),
        sa.Column("catalog_version_id", sa.Uuid(), nullable=False),
        sa.Column("catalog_version", sa.String(length=80), nullable=False),
        sa.Column("meal_slot", sa.String(length=16), nullable=False),
        sa.Column("portion_description", sa.String(length=120), nullable=False),
        sa.Column("portion_grams", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("method_tags", sa.Text(), nullable=False),
        sa.Column("flavour_tags", sa.Text(), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("source_reference", sa.Text(), nullable=False),
        sa.Column("license_name", sa.String(length=80), nullable=False),
        sa.Column("audit_status", sa.String(length=24), nullable=False),
        sa.Column("audited_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("audited_by_role", sa.String(length=48), nullable=False),
        sa.Column("audit_version", sa.String(length=80), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("stable_id = btrim(stable_id) AND stable_id <> ''", name="ck_controlled_recipes_stable_id"),
        sa.CheckConstraint("display_name = btrim(display_name) AND display_name <> ''", name="ck_controlled_recipes_display_name"),
        sa.CheckConstraint("recipe_version = btrim(recipe_version) AND recipe_version <> ''", name="ck_controlled_recipes_recipe_version"),
        sa.CheckConstraint("catalog_version = btrim(catalog_version) AND catalog_version <> ''", name="ck_controlled_recipes_catalog_version"),
        sa.CheckConstraint("meal_slot IN ('breakfast', 'lunch', 'dinner')", name="ck_controlled_recipes_meal_slot"),
        sa.CheckConstraint("portion_description = btrim(portion_description) AND portion_description <> ''", name="ck_controlled_recipes_portion_description"),
        sa.CheckConstraint("portion_grams > 0", name="ck_controlled_recipes_portion_grams_positive"),
        sa.CheckConstraint("method_tags = btrim(method_tags) AND method_tags <> ''", name="ck_controlled_recipes_method_tags"),
        sa.CheckConstraint("flavour_tags = btrim(flavour_tags) AND flavour_tags <> ''", name="ck_controlled_recipes_flavour_tags"),
        sa.CheckConstraint("source_kind = 'project_authored'", name="ck_controlled_recipes_project_authored"),
        sa.CheckConstraint("source_reference = btrim(source_reference) AND source_reference <> ''", name="ck_controlled_recipes_source_reference"),
        sa.CheckConstraint("license_name = 'LicenseRef-Project-Authored-v1'", name="ck_controlled_recipes_license"),
        sa.CheckConstraint("audit_status = 'approved'", name="ck_controlled_recipes_audit_status"),
        sa.CheckConstraint("audited_by_role = 'nutrition_catalog_reviewer'", name="ck_controlled_recipes_auditor_role"),
        sa.CheckConstraint("audit_version = btrim(audit_version) AND audit_version <> ''", name="ck_controlled_recipes_audit_version"),
        sa.ForeignKeyConstraint(["catalog_version_id"], ["nutrition_catalog_versions.id"], name="fk_controlled_recipes_catalog_version", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_controlled_recipes"),
        sa.UniqueConstraint("stable_id", "recipe_version", name="uq_controlled_recipes_stable_version"),
    )
    op.create_index("ix_controlled_recipes_active_catalog_slot", "controlled_recipes", ["catalog_version_id", "meal_slot"], unique=False, postgresql_where=sa.text("is_active"))
    op.create_table(
        "controlled_recipe_ingredients",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recipe_id", sa.Uuid(), nullable=False),
        sa.Column("food_catalog_item_id", sa.Uuid(), nullable=False),
        sa.Column("catalog_version", sa.String(length=80), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("grams", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("portion_description", sa.String(length=120), nullable=False),
        sa.CheckConstraint("position >= 0", name="ck_controlled_recipe_ingredients_position"),
        sa.CheckConstraint("catalog_version = btrim(catalog_version) AND catalog_version <> ''", name="ck_controlled_recipe_ingredients_catalog_version"),
        sa.CheckConstraint("portion_description = btrim(portion_description) AND portion_description <> ''", name="ck_controlled_recipe_ingredients_portion_description"),
        sa.CheckConstraint("grams > 0", name="ck_controlled_recipe_ingredients_grams_positive"),
        sa.ForeignKeyConstraint(["recipe_id"], ["controlled_recipes.id"], name="fk_controlled_recipe_ingredients_recipe", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["food_catalog_item_id"], ["food_catalog_items.id"], name="fk_controlled_recipe_ingredients_food", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_controlled_recipe_ingredients"),
        sa.UniqueConstraint("recipe_id", "position", name="uq_controlled_recipe_ingredients_position"),
    )
    op.create_index("ix_controlled_recipe_ingredients_recipe", "controlled_recipe_ingredients", ["recipe_id", "position"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_controlled_recipe_ingredients_recipe", table_name="controlled_recipe_ingredients")
    op.drop_table("controlled_recipe_ingredients")
    op.drop_index("ix_controlled_recipes_active_catalog_slot", table_name="controlled_recipes")
    op.drop_table("controlled_recipes")
