"""Allow recipe candidates to reference reviewed admin catalog publications."""

from alembic import op
import sqlalchemy as sa


revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "managed_recipe_candidates",
        sa.Column("catalog_publication_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_managed_recipe_candidates_catalog_publication",
        "managed_recipe_candidates",
        "catalog_publications",
        ["catalog_publication_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.add_column(
        "managed_recipe_candidates",
        sa.Column("catalog_food_name", sa.String(200), nullable=True),
    )
    op.add_column(
        "managed_recipe_candidates",
        sa.Column("nutrition_catalog_version", sa.String(80), nullable=True),
    )
    # Existing candidates have an imported catalog reference.  Preserve its exact
    # version before making either reference shape legal.
    op.execute(
        "UPDATE managed_recipe_candidates AS candidate "
        "SET catalog_food_name = food.canonical_name, "
        "nutrition_catalog_version = version.version "
        "FROM food_catalog_items AS food "
        "JOIN nutrition_catalog_versions AS version ON version.id = food.catalog_version_id "
        "WHERE candidate.food_catalog_item_id = food.id"
    )
    op.alter_column("managed_recipe_candidates", "catalog_food_name", nullable=False)
    op.alter_column("managed_recipe_candidates", "nutrition_catalog_version", nullable=False)
    op.alter_column("managed_recipe_candidates", "food_catalog_item_id", nullable=True)
    op.create_check_constraint(
        "ck_managed_recipe_candidates_one_catalog_reference",
        "managed_recipe_candidates",
        "(food_catalog_item_id IS NOT NULL AND catalog_publication_id IS NULL) "
        "OR (food_catalog_item_id IS NULL AND catalog_publication_id IS NOT NULL)",
    )
    op.drop_index(
        "ix_managed_recipe_candidates_planning_eligibility",
        table_name="managed_recipe_candidates",
    )
    op.create_index(
        "ix_managed_recipe_candidates_planning_eligibility",
        "managed_recipe_candidates",
        ["meal_slot", "food_catalog_item_id", "catalog_publication_id"],
        postgresql_where=sa.text("status = 'enabled' AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    # Rows linked to admin publications cannot be represented by the old schema.
    op.execute(
        "DELETE FROM managed_recipe_candidates "
        "WHERE catalog_publication_id IS NOT NULL"
    )
    op.drop_index(
        "ix_managed_recipe_candidates_planning_eligibility",
        table_name="managed_recipe_candidates",
    )
    op.create_index(
        "ix_managed_recipe_candidates_planning_eligibility",
        "managed_recipe_candidates",
        ["meal_slot", "food_catalog_item_id"],
        postgresql_where=sa.text("status = 'enabled' AND deleted_at IS NULL"),
    )
    op.drop_constraint(
        "ck_managed_recipe_candidates_one_catalog_reference",
        "managed_recipe_candidates",
        type_="check",
    )
    op.alter_column("managed_recipe_candidates", "food_catalog_item_id", nullable=False)
    op.drop_column("managed_recipe_candidates", "nutrition_catalog_version")
    op.drop_column("managed_recipe_candidates", "catalog_food_name")
    op.drop_constraint(
        "fk_managed_recipe_candidates_catalog_publication",
        "managed_recipe_candidates",
        type_="foreignkey",
    )
    op.drop_column("managed_recipe_candidates", "catalog_publication_id")
