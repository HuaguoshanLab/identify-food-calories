"""Persist user-confirmed meal slots; historical records remain unclassified."""
from alembic import op
import sqlalchemy as sa

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("meal_records", sa.Column("meal_slot", sa.String(16), nullable=True))
    op.create_check_constraint("ck_meal_records_meal_slot", "meal_records", "meal_slot IS NULL OR meal_slot IN ('breakfast', 'lunch', 'dinner', 'snack')")


def downgrade() -> None:
    op.drop_constraint("ck_meal_records_meal_slot", "meal_records", type_="check")
    op.drop_column("meal_records", "meal_slot")
