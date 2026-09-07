"""Create admin-managed prepared-dish candidates without duplicating nutrition values."""

from alembic import op
import sqlalchemy as sa


revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "managed_recipe_candidates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("food_catalog_item_id", sa.Uuid(), sa.ForeignKey("food_catalog_items.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("meal_slot", sa.String(16), nullable=False),
        sa.Column("portion_grams", sa.Numeric(14, 6), nullable=False),
        sa.Column("portion_description", sa.String(120), nullable=False),
        sa.Column("method_tags", sa.Text(), nullable=False),
        sa.Column("flavour_tags", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("meal_slot IN ('breakfast', 'lunch', 'dinner', 'snack')", name="ck_managed_recipe_candidates_meal_slot"),
        sa.CheckConstraint("portion_grams > 0", name="ck_managed_recipe_candidates_portion_grams_positive"),
        sa.CheckConstraint("portion_description = btrim(portion_description) AND portion_description <> ''", name="ck_managed_recipe_candidates_portion_description"),
        sa.CheckConstraint("method_tags = btrim(method_tags) AND method_tags <> ''", name="ck_managed_recipe_candidates_method_tags"),
        sa.CheckConstraint("flavour_tags = btrim(flavour_tags) AND flavour_tags <> ''", name="ck_managed_recipe_candidates_flavour_tags"),
        sa.CheckConstraint("status IN ('pending', 'enabled', 'disabled')", name="ck_managed_recipe_candidates_status"),
        sa.CheckConstraint("revision >= 1", name="ck_managed_recipe_candidates_revision"),
    )
    op.create_index(
        "ix_managed_recipe_candidates_planning_eligibility", "managed_recipe_candidates", ["meal_slot", "food_catalog_item_id"],
        postgresql_where=sa.text("status = 'enabled' AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_managed_recipe_candidates_planning_eligibility", table_name="managed_recipe_candidates")
    op.drop_table("managed_recipe_candidates")
