"""Persist immutable nutrition catalog content hashes.

Revision ID: 0005
Revises: 0004
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "nutrition_catalog_versions",
        sa.Column("content_hash", sa.String(length=64), nullable=False),
    )
    op.create_unique_constraint(
        "uq_nutrition_catalog_versions_content_hash",
        "nutrition_catalog_versions",
        ["content_hash"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_nutrition_catalog_versions_content_hash",
        "nutrition_catalog_versions",
        type_="unique",
    )
    op.drop_column("nutrition_catalog_versions", "content_hash")
