"""Add immutable catalog publication evidence and future-use eligibility history.

Revision ID: 0018
Revises: 0017
Create Date: 2026-09-03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("catalog_draft_reviews", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("draft_id", sa.Uuid(), nullable=False), sa.Column("draft_revision", sa.Integer(), nullable=False), sa.Column("snapshot", sa.JSON(), nullable=False), sa.Column("content_hash", sa.String(length=64), nullable=False), sa.Column("actor_identifier", sa.String(length=320), nullable=False), sa.Column("reason", sa.String(length=500), nullable=False), sa.Column("command_key", sa.String(length=160), nullable=False), sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False), sa.PrimaryKeyConstraint("id", name="pk_catalog_draft_reviews"), sa.ForeignKeyConstraint(["draft_id"], ["catalog_drafts.id"], ondelete="RESTRICT"), sa.UniqueConstraint("draft_id", "draft_revision", name="uq_catalog_draft_reviews_revision"), sa.UniqueConstraint("command_key", name="uq_catalog_draft_reviews_command_key"), sa.CheckConstraint("draft_revision > 0", name="ck_catalog_draft_reviews_revision_positive"))
    op.create_table("catalog_publications", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("draft_id", sa.Uuid(), nullable=False), sa.Column("review_id", sa.Uuid(), nullable=False), sa.Column("draft_revision", sa.Integer(), nullable=False), sa.Column("snapshot", sa.JSON(), nullable=False), sa.Column("content_hash", sa.String(length=64), nullable=False), sa.Column("actor_identifier", sa.String(length=320), nullable=False), sa.Column("reason", sa.String(length=500), nullable=False), sa.Column("command_key", sa.String(length=160), nullable=False), sa.Column("published_at", sa.DateTime(timezone=True), nullable=False), sa.PrimaryKeyConstraint("id", name="pk_catalog_publications"), sa.ForeignKeyConstraint(["draft_id"], ["catalog_drafts.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["review_id"], ["catalog_draft_reviews.id"], ondelete="RESTRICT"), sa.UniqueConstraint("command_key", name="uq_catalog_publications_command_key"), sa.UniqueConstraint("draft_id", "draft_revision", name="uq_catalog_publications_revision"), sa.CheckConstraint("draft_revision > 0", name="ck_catalog_publications_revision_positive"))
    op.create_table("catalog_active_publications", sa.Column("draft_id", sa.Uuid(), nullable=False), sa.Column("publication_id", sa.Uuid(), nullable=False), sa.Column("advanced_at", sa.DateTime(timezone=True), nullable=False), sa.PrimaryKeyConstraint("draft_id", name="pk_catalog_active_publications"), sa.UniqueConstraint("publication_id", name="uq_catalog_active_publications_publication"), sa.ForeignKeyConstraint(["draft_id"], ["catalog_drafts.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["publication_id"], ["catalog_publications.id"], ondelete="RESTRICT"))
    op.create_table("catalog_publication_eligibilities", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("publication_id", sa.Uuid(), nullable=False), sa.Column("status", sa.String(length=16), nullable=False), sa.Column("actor_identifier", sa.String(length=320), nullable=False), sa.Column("reason", sa.String(length=500), nullable=False), sa.Column("command_key", sa.String(length=160), nullable=False), sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False), sa.PrimaryKeyConstraint("id", name="pk_catalog_publication_eligibilities"), sa.ForeignKeyConstraint(["publication_id"], ["catalog_publications.id"], ondelete="RESTRICT"), sa.UniqueConstraint("command_key", name="uq_catalog_publication_eligibilities_command_key"), sa.CheckConstraint("status IN ('eligible', 'disqualified')", name="ck_catalog_publication_eligibilities_status"), sa.CheckConstraint("reason = btrim(reason) AND reason <> ''", name="ck_catalog_publication_eligibilities_reason"))
    op.create_index("ix_catalog_publication_eligibilities_latest", "catalog_publication_eligibilities", ["publication_id", "occurred_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_catalog_publication_eligibilities_latest", table_name="catalog_publication_eligibilities")
    op.drop_table("catalog_publication_eligibilities")
    op.drop_table("catalog_active_publications")
    op.drop_table("catalog_publications")
    op.drop_table("catalog_draft_reviews")
