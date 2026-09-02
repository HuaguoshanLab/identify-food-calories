"""Add mutable, revisioned nutrition catalog drafts with server audit evidence.

Revision ID: 0017
Revises: 0016
Create Date: 2026-09-02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "catalog_drafts",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("canonical_name", sa.String(length=200), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=False), sa.Column("energy_kcal_per_100g", sa.Numeric(14, 6), nullable=False),
        sa.Column("protein_g_per_100g", sa.Numeric(14, 6), nullable=False), sa.Column("fat_g_per_100g", sa.Numeric(14, 6), nullable=False),
        sa.Column("carbohydrate_g_per_100g", sa.Numeric(14, 6), nullable=False), sa.Column("source_name", sa.String(length=120), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=False), sa.Column("authorization_status", sa.String(length=16), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.PrimaryKeyConstraint("id", name="pk_catalog_drafts"),
        sa.CheckConstraint("canonical_name = btrim(canonical_name) AND canonical_name <> ''", name="ck_catalog_drafts_name"),
        sa.CheckConstraint("source_name = btrim(source_name) AND source_name <> ''", name="ck_catalog_drafts_source_name"),
        sa.CheckConstraint("source_url LIKE 'https://%'", name="ck_catalog_drafts_source_url_https"),
        sa.CheckConstraint("authorization_status IN ('authorized', 'pending', 'revoked')", name="ck_catalog_drafts_authorization"),
        sa.CheckConstraint("revision > 0", name="ck_catalog_drafts_revision_positive"),
        sa.CheckConstraint("energy_kcal_per_100g >= 0 AND protein_g_per_100g >= 0 AND fat_g_per_100g >= 0 AND carbohydrate_g_per_100g >= 0", name="ck_catalog_drafts_nutrients_nonnegative"),
    )
    op.create_table(
        "catalog_draft_change_sets",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("draft_id", sa.Uuid(), nullable=False),
        sa.Column("actor_identifier", sa.String(length=320), nullable=False), sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False), sa.Column("command_key", sa.String(length=160), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False), sa.Column("revision_before", sa.Integer(), nullable=False),
        sa.Column("revision_after", sa.Integer(), nullable=False), sa.Column("before_diff", sa.JSON(), nullable=False), sa.Column("after_diff", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["draft_id"], ["catalog_drafts.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id", name="pk_catalog_draft_change_sets"),
        sa.UniqueConstraint("command_key", name="uq_catalog_draft_change_sets_command_key"),
        sa.CheckConstraint("actor_identifier = btrim(actor_identifier) AND actor_identifier <> ''", name="ck_catalog_draft_changes_actor"),
        sa.CheckConstraint("reason = btrim(reason) AND reason <> ''", name="ck_catalog_draft_changes_reason"),
        sa.CheckConstraint("command_key = btrim(command_key) AND command_key <> ''", name="ck_catalog_draft_changes_command"),
        sa.CheckConstraint("revision_before >= 0 AND revision_after > revision_before", name="ck_catalog_draft_changes_revision"),
    )
    op.create_index("ix_catalog_draft_change_sets_draft_revision", "catalog_draft_change_sets", ["draft_id", "revision_after"])
    op.create_table(
        "catalog_draft_revisions",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("draft_id", sa.Uuid(), nullable=False), sa.Column("change_set_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False), sa.Column("snapshot", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["draft_id"], ["catalog_drafts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["change_set_id"], ["catalog_draft_change_sets.id"], ondelete="RESTRICT"), sa.PrimaryKeyConstraint("id", name="pk_catalog_draft_revisions"),
        sa.UniqueConstraint("draft_id", "revision", name="uq_catalog_draft_revisions_draft_revision"), sa.CheckConstraint("revision > 0", name="ck_catalog_draft_revisions_positive"),
    )


def downgrade() -> None:
    op.drop_table("catalog_draft_revisions")
    op.drop_index("ix_catalog_draft_change_sets_draft_revision", table_name="catalog_draft_change_sets")
    op.drop_table("catalog_draft_change_sets")
    op.drop_table("catalog_drafts")
