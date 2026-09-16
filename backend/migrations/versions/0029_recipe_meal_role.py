"""Explicit administrator-authored meal roles; preserve legacy eligibility.

Revision ID: 0029
Revises: 0028
"""

from alembic import op
import sqlalchemy as sa

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("managed_recipe_candidates", sa.Column(
        "meal_role", sa.String(16), nullable=False, server_default="standalone",
    ))
    op.create_check_constraint(
        "ck_managed_recipe_candidates_meal_role", "managed_recipe_candidates",
        "meal_role IN ('standalone', 'staple', 'protein', 'vegetable', 'side', 'drink')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_managed_recipe_candidates_meal_role", "managed_recipe_candidates", type_="check")
    op.drop_column("managed_recipe_candidates", "meal_role")
