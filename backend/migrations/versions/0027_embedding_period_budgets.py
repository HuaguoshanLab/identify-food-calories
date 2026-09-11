"""Persist atomic, cross-process embedding cost reservations.

Revision ID: 0027
Revises: 0026
"""

from alembic import op
import sqlalchemy as sa


revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "embedding_provider_period_budgets",
        sa.Column("period_key", sa.String(length=7), nullable=False),
        sa.Column("reserved_cny", sa.Numeric(18, 8), nullable=False),
        sa.Column("spent_cny", sa.Numeric(18, 8), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("period_key", name="pk_embedding_provider_period_budgets"),
        sa.CheckConstraint("period_key ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'", name="ck_embedding_provider_period_budgets_key"),
        sa.CheckConstraint("reserved_cny >= 0", name="ck_embedding_provider_period_budgets_reserved"),
        sa.CheckConstraint("spent_cny >= 0", name="ck_embedding_provider_period_budgets_spent"),
    )


def downgrade() -> None:
    op.drop_table("embedding_provider_period_budgets")
