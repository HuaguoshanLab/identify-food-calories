"""Create versioned, isolated catalog hybrid-search storage contracts.

Revision ID: 0025
Revises: 0024
"""

from alembic import op
import sqlalchemy as sa


revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


class _Vector1024(sa.types.UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **_kw: object) -> str:
        return "vector(1024)"


def _audit_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("actor_identifier", sa.String(length=320), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("command_key", sa.String(length=160), nullable=False),
    ]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    vector = _Vector1024()

    op.create_table(
        "catalog_search_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("publication_id", sa.Uuid(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["publication_id"], ["catalog_publications.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_catalog_search_versions"),
        sa.UniqueConstraint("publication_id", "content_hash", name="uq_catalog_search_versions_publication_content"),
    )
    op.create_table(
        "catalog_vector_spaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("embedding_model", sa.String(length=120), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("adapter_version", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_catalog_vector_spaces"),
        sa.UniqueConstraint("embedding_model", "embedding_dimension", "adapter_version", name="uq_catalog_vector_spaces_identity"),
        sa.CheckConstraint("embedding_dimension = 1024", name="ck_catalog_vector_spaces_dimension"),
        sa.CheckConstraint("embedding_model = btrim(embedding_model) AND embedding_model <> ''", name="ck_catalog_vector_spaces_model"),
        sa.CheckConstraint("adapter_version = btrim(adapter_version) AND adapter_version <> ''", name="ck_catalog_vector_spaces_adapter"),
    )
    op.create_table(
        "catalog_active_vector_spaces",
        sa.Column("pointer_key", sa.String(length=32), nullable=False),
        sa.Column("vector_space_id", sa.Uuid(), nullable=False),
        sa.Column("advanced_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["vector_space_id"], ["catalog_vector_spaces.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("pointer_key", name="pk_catalog_active_vector_spaces"),
        sa.UniqueConstraint("vector_space_id", name="uq_catalog_active_vector_spaces_vector_space"),
        sa.CheckConstraint("pointer_key = 'catalog'", name="ck_catalog_active_vector_spaces_singleton"),
    )
    op.create_table(
        "catalog_search_names",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("publication_id", sa.Uuid(), nullable=False),
        sa.Column("search_version_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("normalized_name", sa.String(length=200), nullable=False),
        sa.Column("name_kind", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["publication_id"], ["catalog_publications.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["search_version_id"], ["catalog_search_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_catalog_search_names"),
        sa.UniqueConstraint("publication_id", "normalized_name", name="uq_catalog_search_names_publication_normalized"),
        sa.CheckConstraint("name_kind IN ('canonical', 'controlled_alias')", name="ck_catalog_search_names_kind"),
        sa.CheckConstraint("display_name = btrim(display_name) AND display_name <> ''", name="ck_catalog_search_names_display"),
        sa.CheckConstraint("normalized_name = btrim(normalized_name) AND normalized_name <> ''", name="ck_catalog_search_names_normalized"),
    )
    op.create_index("ix_catalog_search_names_normalized_trgm", "catalog_search_names", ["normalized_name"], postgresql_using="gist", postgresql_ops={"normalized_name": "gist_trgm_ops"})
    op.create_table(
        "catalog_search_embeddings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("publication_id", sa.Uuid(), nullable=False),
        sa.Column("name_id", sa.Uuid(), nullable=False),
        sa.Column("vector_space_id", sa.Uuid(), nullable=False),
        sa.Column("embedding", vector, nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["publication_id"], ["catalog_publications.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["name_id"], ["catalog_search_names.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["vector_space_id"], ["catalog_vector_spaces.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_catalog_search_embeddings"),
        sa.UniqueConstraint("publication_id", "name_id", "vector_space_id", name="uq_catalog_search_embeddings_business_key"),
        sa.CheckConstraint("status = 'ready'", name="ck_catalog_search_embeddings_status"),
    )
    op.create_index("ix_catalog_search_embeddings_ready_cosine", "catalog_search_embeddings", ["embedding"], postgresql_using="hnsw", postgresql_ops={"embedding": "vector_cosine_ops"}, postgresql_where=sa.text("status = 'ready'"))
    op.create_table(
        "catalog_search_relation_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_name_id", sa.Uuid(), nullable=False),
        sa.Column("target_name_id", sa.Uuid(), nullable=False),
        sa.Column("relation", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        *_audit_columns(),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_name_id"], ["catalog_search_names.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["target_name_id"], ["catalog_search_names.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_catalog_search_relation_evidence"),
        sa.UniqueConstraint("command_key", name="uq_catalog_search_relation_evidence_command_key"),
        sa.CheckConstraint("relation IN ('name_variant', 'regional_preparation_variant', 'same_category_food')", name="ck_catalog_search_relation_evidence_relation"),
        sa.CheckConstraint("status IN ('active', 'revoked')", name="ck_catalog_search_relation_evidence_status"),
        sa.CheckConstraint("source_name_id <> target_name_id", name="ck_catalog_search_relation_evidence_distinct_names"),
    )
    op.create_index("ix_catalog_search_relation_evidence_current", "catalog_search_relation_evidence", ["source_name_id", "target_name_id", "occurred_at", "id"])
    op.create_table(
        "catalog_embedding_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("publication_id", sa.Uuid(), nullable=False),
        sa.Column("name_id", sa.Uuid(), nullable=False),
        sa.Column("vector_space_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("not_before", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_owner", sa.String(length=160), nullable=True),
        sa.Column("leased_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["publication_id"], ["catalog_publications.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["name_id"], ["catalog_search_names.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["vector_space_id"], ["catalog_vector_spaces.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_catalog_embedding_jobs"),
        sa.UniqueConstraint("publication_id", "name_id", "vector_space_id", name="uq_catalog_embedding_jobs_business_key"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_catalog_embedding_jobs_attempt_nonnegative"),
        sa.CheckConstraint("max_attempts > 0 AND attempt_count <= max_attempts", name="ck_catalog_embedding_jobs_finite_attempts"),
        sa.CheckConstraint("status IN ('pending', 'leased', 'completed', 'failed')", name="ck_catalog_embedding_jobs_status"),
    )
    op.create_index("ix_catalog_embedding_jobs_due", "catalog_embedding_jobs", ["not_before", "id"], postgresql_where=sa.text("status IN ('pending', 'leased')"))
    op.create_table(
        "catalog_vector_space_builds",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vector_space_id", sa.Uuid(), nullable=False),
        sa.Column("requested_by", sa.String(length=320), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("command_key", sa.String(length=160), nullable=False),
        sa.Column("snapshot_manifest", sa.JSON(), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("expected_name_count", sa.Integer(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["vector_space_id"], ["catalog_vector_spaces.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_catalog_vector_space_builds"),
        sa.UniqueConstraint("command_key", name="uq_catalog_vector_space_builds_command_key"),
        sa.CheckConstraint("expected_name_count >= 0", name="ck_catalog_vector_space_builds_expected_count"),
    )
    op.create_table(
        "catalog_vector_space_build_completions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("build_id", sa.Uuid(), nullable=False),
        sa.Column("completed_name_count", sa.Integer(), nullable=False),
        sa.Column("completion_hash", sa.String(length=64), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["build_id"], ["catalog_vector_space_builds.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_catalog_vector_space_build_completions"),
        sa.UniqueConstraint("build_id", name="uq_catalog_vector_space_build_completions_build"),
        sa.CheckConstraint("completed_name_count >= 0", name="ck_catalog_vector_space_build_completions_count"),
    )
    op.create_table(
        "catalog_embedding_retry_commands",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("publication_id", sa.Uuid(), nullable=False),
        sa.Column("name_id", sa.Uuid(), nullable=False),
        sa.Column("vector_space_id", sa.Uuid(), nullable=False),
        *_audit_columns(),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["publication_id"], ["catalog_publications.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["name_id"], ["catalog_search_names.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["vector_space_id"], ["catalog_vector_spaces.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_catalog_embedding_retry_commands"),
        sa.UniqueConstraint("command_key", name="uq_catalog_embedding_retry_commands_command_key"),
    )
    op.create_table(
        "catalog_vector_space_activation_approvals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("build_id", sa.Uuid(), nullable=False),
        sa.Column("release_hash", sa.String(length=64), nullable=False),
        sa.Column("dataset_hash", sa.String(length=64), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("retrieval_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding_hash", sa.String(length=64), nullable=False),
        sa.Column("approver_identifier", sa.String(length=320), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("command_key", sa.String(length=160), nullable=False),
        sa.ForeignKeyConstraint(["build_id"], ["catalog_vector_space_builds.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_catalog_vector_space_activation_approvals"),
        sa.UniqueConstraint("command_key", name="uq_catalog_vector_space_activation_approvals_command_key"),
    )


def downgrade() -> None:
    op.drop_table("catalog_vector_space_activation_approvals")
    op.drop_table("catalog_embedding_retry_commands")
    op.drop_table("catalog_vector_space_build_completions")
    op.drop_table("catalog_vector_space_builds")
    op.drop_index("ix_catalog_embedding_jobs_due", table_name="catalog_embedding_jobs")
    op.drop_table("catalog_embedding_jobs")
    op.drop_index("ix_catalog_search_relation_evidence_current", table_name="catalog_search_relation_evidence")
    op.drop_table("catalog_search_relation_evidence")
    op.drop_index("ix_catalog_search_embeddings_ready_cosine", table_name="catalog_search_embeddings")
    op.drop_table("catalog_search_embeddings")
    op.drop_index("ix_catalog_search_names_normalized_trgm", table_name="catalog_search_names")
    op.drop_table("catalog_search_names")
    op.drop_table("catalog_active_vector_spaces")
    op.drop_table("catalog_vector_spaces")
    op.drop_table("catalog_search_versions")
    # pg_trgm is a database-wide prerequisite, not an object owned by this
    # feature migration.  Removing it here could break another module during a
    # rollback, so deployment governance owns its lifecycle.
