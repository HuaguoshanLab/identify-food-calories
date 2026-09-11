"""Make retrieval policy part of immutable catalog vector-space identity.

Revision ID: 0026
Revises: 0025
"""

from alembic import op
import sqlalchemy as sa


revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


_LEGACY_RETRIEVAL_VERSION = "hybrid-v1"


def upgrade() -> None:
    """Backfill pre-06.3 rows to the only deployed retrieval policy, then constrain."""

    op.add_column(
        "catalog_vector_spaces",
        sa.Column("retrieval_version", sa.String(length=80), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE catalog_vector_spaces SET retrieval_version = :version "
            "WHERE retrieval_version IS NULL"
        ).bindparams(version=_LEGACY_RETRIEVAL_VERSION)
    )
    op.alter_column("catalog_vector_spaces", "retrieval_version", nullable=False)
    op.create_check_constraint(
        "ck_catalog_vector_spaces_retrieval",
        "catalog_vector_spaces",
        "retrieval_version = btrim(retrieval_version) AND retrieval_version <> ''",
    )
    op.drop_constraint(
        "uq_catalog_vector_spaces_identity",
        "catalog_vector_spaces",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_catalog_vector_spaces_identity",
        "catalog_vector_spaces",
        ["embedding_model", "embedding_dimension", "adapter_version", "retrieval_version"],
    )

    op.add_column(
        "catalog_vector_space_builds",
        sa.Column("retrieval_version", sa.String(length=80), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE catalog_vector_space_builds SET retrieval_version = :version "
            "WHERE retrieval_version IS NULL"
        ).bindparams(version=_LEGACY_RETRIEVAL_VERSION)
    )
    op.alter_column("catalog_vector_space_builds", "retrieval_version", nullable=False)
    op.create_check_constraint(
        "ck_catalog_vector_space_builds_retrieval",
        "catalog_vector_space_builds",
        "retrieval_version = btrim(retrieval_version) AND retrieval_version <> ''",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_catalog_vector_space_builds_retrieval",
        "catalog_vector_space_builds",
        type_="check",
    )
    op.drop_column("catalog_vector_space_builds", "retrieval_version")
    op.drop_constraint(
        "uq_catalog_vector_spaces_identity",
        "catalog_vector_spaces",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_catalog_vector_spaces_identity",
        "catalog_vector_spaces",
        ["embedding_model", "embedding_dimension", "adapter_version"],
    )
    op.drop_constraint(
        "ck_catalog_vector_spaces_retrieval",
        "catalog_vector_spaces",
        type_="check",
    )
    op.drop_column("catalog_vector_spaces", "retrieval_version")
