"""Allow a managed candidate to serve several meal slots without duplication."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("managed_recipe_candidates", sa.Column("meal_slots", postgresql.ARRAY(sa.String(16)), nullable=True))
    op.execute("UPDATE managed_recipe_candidates SET meal_slots = ARRAY[meal_slot]")
    op.alter_column("managed_recipe_candidates", "meal_slots", nullable=False)
    op.create_check_constraint("ck_managed_recipe_candidates_meal_slots", "managed_recipe_candidates", "cardinality(meal_slots) BETWEEN 1 AND 4 AND meal_slots <@ ARRAY['breakfast','lunch','dinner','snack']::varchar[] AND array_position(meal_slots, NULL) IS NULL")
    op.drop_index("ix_managed_recipe_candidates_planning_eligibility", table_name="managed_recipe_candidates")
    op.drop_constraint("ck_managed_recipe_candidates_meal_slot", "managed_recipe_candidates", type_="check")
    op.drop_column("managed_recipe_candidates", "meal_slot")
    op.create_index("ix_managed_recipe_candidates_planning_eligibility", "managed_recipe_candidates", ["food_catalog_item_id", "catalog_publication_id"], postgresql_where=sa.text("status = 'enabled' AND deleted_at IS NULL"))


def downgrade():
    # Never silently discard a second applicable slot during rollback.
    op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM managed_recipe_candidates WHERE cardinality(meal_slots) <> 1) THEN RAISE EXCEPTION 'Back up and resolve multi-slot candidates before downgrade'; END IF; END $$")
    op.add_column("managed_recipe_candidates", sa.Column("meal_slot", sa.String(16), nullable=True))
    op.execute("UPDATE managed_recipe_candidates SET meal_slot = meal_slots[1]")
    op.alter_column("managed_recipe_candidates", "meal_slot", nullable=False)
    op.drop_index("ix_managed_recipe_candidates_planning_eligibility", table_name="managed_recipe_candidates")
    op.drop_constraint("ck_managed_recipe_candidates_meal_slots", "managed_recipe_candidates", type_="check")
    op.drop_column("managed_recipe_candidates", "meal_slots")
    op.create_check_constraint("ck_managed_recipe_candidates_meal_slot", "managed_recipe_candidates", "meal_slot IN ('breakfast', 'lunch', 'dinner', 'snack')")
    op.create_index("ix_managed_recipe_candidates_planning_eligibility", "managed_recipe_candidates", ["meal_slot", "food_catalog_item_id", "catalog_publication_id"], postgresql_where=sa.text("status = 'enabled' AND deleted_at IS NULL"))
