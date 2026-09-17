"""Retire the mutable legacy role; classification is the sole selection source."""
from alembic import op
import sqlalchemy as sa

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade():
    # Preserve explicit pre-classification roles before dropping their old column.
    # Existing annotations (including unknown and manually reviewed) are authoritative.
    op.execute("""
        UPDATE managed_recipe_candidates SET classification = jsonb_build_object(
            'version', 'recipe-classification.v1', 'purpose', 'component',
            'role', meal_role, 'ingredient_tags', '[]'::jsonb,
            'basis', 'name_and_legacy_role', 'evidence', '0031迁移保留旧角色；食材未确认'
        ) WHERE classification IS NULL AND meal_role <> 'standalone'
    """)
    op.drop_constraint("ck_managed_recipe_candidates_meal_role", "managed_recipe_candidates", type_="check")
    op.drop_column("managed_recipe_candidates", "meal_role")


def downgrade():
    # A downgrade recreates a compatible projection, not the deleted historical values.
    op.add_column("managed_recipe_candidates", sa.Column("meal_role", sa.String(16), nullable=False, server_default="standalone"))
    op.execute("""
        UPDATE managed_recipe_candidates SET meal_role = classification->>'role'
        WHERE classification->>'purpose' = 'component'
          AND classification->>'role' IN ('staple', 'protein', 'vegetable', 'side', 'drink')
    """)
    op.create_check_constraint("ck_managed_recipe_candidates_meal_role", "managed_recipe_candidates", "meal_role IN ('standalone', 'staple', 'protein', 'vegetable', 'side', 'drink')")
