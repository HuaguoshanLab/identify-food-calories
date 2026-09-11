"""Derived ORM evidence for isolated catalog hybrid-search vector spaces."""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.auth.models import Base


class CatalogSearchVersion(Base):
    """Immutable content-addressed search contract for one publication."""

    __tablename__ = "catalog_search_versions"
    __table_args__ = (UniqueConstraint("publication_id", "content_hash", name="uq_catalog_search_versions_publication_content"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    publication_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("catalog_publications.id", ondelete="RESTRICT"), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CatalogVectorSpace(Base):
    """A non-interchangeable model, dimension and adapter identity."""

    __tablename__ = "catalog_vector_spaces"
    __table_args__ = (
        UniqueConstraint("embedding_model", "embedding_dimension", "adapter_version", "retrieval_version", name="uq_catalog_vector_spaces_identity"),
        CheckConstraint("embedding_dimension = 1024", name="ck_catalog_vector_spaces_dimension"),
        CheckConstraint("embedding_model = btrim(embedding_model) AND embedding_model <> ''", name="ck_catalog_vector_spaces_model"),
        CheckConstraint("adapter_version = btrim(adapter_version) AND adapter_version <> ''", name="ck_catalog_vector_spaces_adapter"),
        CheckConstraint("retrieval_version = btrim(retrieval_version) AND retrieval_version <> ''", name="ck_catalog_vector_spaces_retrieval"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    embedding_model: Mapped[str] = mapped_column(String(120), nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False, default=1024)
    adapter_version: Mapped[str] = mapped_column(String(80), nullable=False)
    retrieval_version: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CatalogActiveVectorSpace(Base):
    """The sole mutable pointer; approval evidence is stored separately."""

    __tablename__ = "catalog_active_vector_spaces"

    pointer_key: Mapped[str] = mapped_column(String(32), primary_key=True, default="catalog")
    vector_space_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("catalog_vector_spaces.id", ondelete="RESTRICT"), nullable=False, unique=True)
    advanced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CatalogSearchName(Base):
    """Controlled canonical or alias name that may receive an embedding job."""

    __tablename__ = "catalog_search_names"
    __table_args__ = (
        UniqueConstraint("publication_id", "normalized_name", name="uq_catalog_search_names_publication_normalized"),
        CheckConstraint("name_kind IN ('canonical', 'controlled_alias')", name="ck_catalog_search_names_kind"),
        Index("ix_catalog_search_names_normalized_trgm", "normalized_name", postgresql_using="gist", postgresql_ops={"normalized_name": "gist_trgm_ops"}),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    publication_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("catalog_publications.id", ondelete="RESTRICT"), nullable=False)
    search_version_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("catalog_search_versions.id", ondelete="RESTRICT"), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CatalogSearchEmbedding(Base):
    """Derived catalog vector; user queries and query vectors are never stored."""

    __tablename__ = "catalog_search_embeddings"
    __table_args__ = (
        UniqueConstraint("publication_id", "name_id", "vector_space_id", name="uq_catalog_search_embeddings_business_key"),
        Index("ix_catalog_search_embeddings_ready_cosine", "embedding", postgresql_using="hnsw", postgresql_ops={"embedding": "vector_cosine_ops"}, postgresql_where="status = 'ready'"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    publication_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("catalog_publications.id", ondelete="RESTRICT"), nullable=False)
    name_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("catalog_search_names.id", ondelete="RESTRICT"), nullable=False)
    vector_space_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("catalog_vector_spaces.id", ondelete="RESTRICT"), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ready")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CatalogSearchRelationEvidence(Base):
    """Append-only controlled proof; revocation adds evidence instead of erasing it."""

    __tablename__ = "catalog_search_relation_evidence"
    __table_args__ = (
        UniqueConstraint("command_key", name="uq_catalog_search_relation_evidence_command_key"),
        CheckConstraint("relation IN ('name_variant', 'regional_preparation_variant', 'same_category_food')", name="ck_catalog_search_relation_evidence_relation"),
        CheckConstraint("status IN ('active', 'revoked')", name="ck_catalog_search_relation_evidence_status"),
        CheckConstraint("source_name_id <> target_name_id", name="ck_catalog_search_relation_evidence_distinct_names"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_name_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("catalog_search_names.id", ondelete="RESTRICT"), nullable=False)
    target_name_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("catalog_search_names.id", ondelete="RESTRICT"), nullable=False)
    relation: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_identifier: Mapped[str] = mapped_column(String(320), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    command_key: Mapped[str] = mapped_column(String(160), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CatalogEmbeddingJob(Base):
    """Recoverable one-name job with a finite retry budget and short lease."""

    __tablename__ = "catalog_embedding_jobs"
    __table_args__ = (
        UniqueConstraint("publication_id", "name_id", "vector_space_id", name="uq_catalog_embedding_jobs_business_key"),
        CheckConstraint("attempt_count >= 0", name="ck_catalog_embedding_jobs_attempt_nonnegative"),
        CheckConstraint("max_attempts > 0 AND attempt_count <= max_attempts", name="ck_catalog_embedding_jobs_finite_attempts"),
        CheckConstraint("status IN ('pending', 'leased', 'completed', 'failed')", name="ck_catalog_embedding_jobs_status"),
        Index("ix_catalog_embedding_jobs_due", "not_before", "id", postgresql_where="status IN ('pending', 'leased')"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    publication_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("catalog_publications.id", ondelete="RESTRICT"), nullable=False)
    name_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("catalog_search_names.id", ondelete="RESTRICT"), nullable=False)
    vector_space_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("catalog_vector_spaces.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    not_before: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lease_owner: Mapped[str | None] = mapped_column(String(160))
    leased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CatalogVectorSpaceBuild(Base):
    """Frozen eligible-name manifest requested before a parallel space build begins."""

    __tablename__ = "catalog_vector_space_builds"
    __table_args__ = (UniqueConstraint("command_key", name="uq_catalog_vector_space_builds_command_key"), CheckConstraint("expected_name_count >= 0", name="ck_catalog_vector_space_builds_expected_count"))

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    vector_space_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("catalog_vector_spaces.id", ondelete="RESTRICT"), nullable=False)
    requested_by: Mapped[str] = mapped_column(String(320), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    command_key: Mapped[str] = mapped_column(String(160), nullable=False)
    retrieval_version: Mapped[str] = mapped_column(String(80), nullable=False)
    snapshot_manifest: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expected_name_count: Mapped[int] = mapped_column(Integer, nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CatalogVectorSpaceBuildCompletion(Base):
    """Completion is immutable evidence separate from the requested manifest."""

    __tablename__ = "catalog_vector_space_build_completions"
    __table_args__ = (UniqueConstraint("build_id", name="uq_catalog_vector_space_build_completions_build"), CheckConstraint("completed_name_count >= 0", name="ck_catalog_vector_space_build_completions_count"))

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    build_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("catalog_vector_space_builds.id", ondelete="RESTRICT"), nullable=False)
    completed_name_count: Mapped[int] = mapped_column(Integer, nullable=False)
    completion_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CatalogEmbeddingRetryCommand(Base):
    """Auditable retry request, kept distinct from mutable job lease state."""

    __tablename__ = "catalog_embedding_retry_commands"
    __table_args__ = (UniqueConstraint("command_key", name="uq_catalog_embedding_retry_commands_command_key"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    publication_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("catalog_publications.id", ondelete="RESTRICT"), nullable=False)
    name_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("catalog_search_names.id", ondelete="RESTRICT"), nullable=False)
    vector_space_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("catalog_vector_spaces.id", ondelete="RESTRICT"), nullable=False)
    actor_identifier: Mapped[str] = mapped_column(String(320), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    command_key: Mapped[str] = mapped_column(String(160), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CatalogVectorSpaceActivationApproval(Base):
    """Frozen release evidence that authorizes, but does not itself switch, a pointer."""

    __tablename__ = "catalog_vector_space_activation_approvals"
    __table_args__ = (UniqueConstraint("command_key", name="uq_catalog_vector_space_activation_approvals_command_key"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    build_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("catalog_vector_space_builds.id", ondelete="RESTRICT"), nullable=False)
    release_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    retrieval_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    approver_identifier: Mapped[str] = mapped_column(String(320), nullable=False)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    command_key: Mapped[str] = mapped_column(String(160), nullable=False)
