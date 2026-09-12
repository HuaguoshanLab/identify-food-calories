"""Persist safe stage metadata for agent runtime failures.

Revision ID: 0028
Revises: 0027
"""

from alembic import op
import sqlalchemy as sa


revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_runs", sa.Column("failure_stage", sa.String(length=80), nullable=True))
    op.add_column("agent_runs", sa.Column("failure_class", sa.String(length=80), nullable=True))


def downgrade() -> None:
    op.drop_column("agent_runs", "failure_class")
    op.drop_column("agent_runs", "failure_stage")
