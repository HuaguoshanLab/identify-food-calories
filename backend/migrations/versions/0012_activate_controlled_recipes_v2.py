"""Retire the unsafe controlled-recipes.v1 candidate set.

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-02

The v1 records remain immutable audit history.  The bootstrap/import path adds
the reviewed v2 rows separately; this migration only ensures an existing v1
deployment cannot continue serving the known-underfloor set during that switch.
"""

from __future__ import annotations

from alembic import op


revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE controlled_recipes "
        "SET is_active = FALSE "
        "WHERE recipe_version = 'controlled-recipes.v1' AND is_active = TRUE"
    )


def downgrade() -> None:
    # Downgrading removes v2 selection policy, so the retained v1 audit records
    # become available again only for a deliberate rollback.
    op.execute(
        "UPDATE controlled_recipes "
        "SET is_active = TRUE "
        "WHERE recipe_version = 'controlled-recipes.v1' AND is_active = FALSE"
    )
