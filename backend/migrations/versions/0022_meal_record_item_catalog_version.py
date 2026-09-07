"""Preserve the nutrition catalog version for every saved meal item."""

from alembic import op
import sqlalchemy as sa


revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "meal_record_items",
        sa.Column("nutrition_catalog_version", sa.String(80), nullable=True),
    )
    op.execute(
        "UPDATE meal_record_items AS item "
        "SET nutrition_catalog_version = record.nutrition_catalog_version "
        "FROM meal_records AS record "
        "WHERE item.record_id = record.id"
    )
    op.alter_column("meal_record_items", "nutrition_catalog_version", nullable=False)


def downgrade() -> None:
    op.drop_column("meal_record_items", "nutrition_catalog_version")
