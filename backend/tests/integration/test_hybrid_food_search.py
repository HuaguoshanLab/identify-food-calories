"""Real PostgreSQL contracts for versioned hybrid catalog retrieval."""

from __future__ import annotations

from sqlalchemy import text


def _columns(db_session, table_name: str) -> dict[str, str]:
    rows = db_session.execute(
        text(
            "SELECT column_name, udt_name "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :table_name"
        ),
        {"table_name": table_name},
    )
    return dict(rows)


def _constraint_definitions(db_session, table_name: str) -> str:
    return "\n".join(
        db_session.scalars(
            text(
                "SELECT pg_get_constraintdef(con.oid) "
                "FROM pg_constraint AS con "
                "JOIN pg_class AS rel ON rel.oid = con.conrelid "
                "JOIN pg_namespace AS nsp ON nsp.oid = rel.relnamespace "
                "WHERE nsp.nspname = 'public' AND rel.relname = :table_name"
            ),
            {"table_name": table_name},
        )
    )


def _index_definitions(db_session, table_name: str) -> str:
    return "\n".join(
        db_session.scalars(
            text("SELECT indexdef FROM pg_indexes WHERE schemaname = 'public' AND tablename = :table_name"),
            {"table_name": table_name},
        )
    )


def test_hybrid_food_search_schema_contract(db_session) -> None:
    """The database, rather than application code, enforces retrieval boundaries."""

    assert db_session.scalar(text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm')"))

    space_columns = _columns(db_session, "catalog_vector_spaces")
    assert {"id", "embedding_model", "embedding_dimension", "adapter_version"} <= space_columns.keys()
    space_constraints = _constraint_definitions(db_session, "catalog_vector_spaces")
    assert "embedding_dimension = 1024" in space_constraints
    assert "embedding_model" in space_constraints and "adapter_version" in space_constraints

    assert {"vector_space_id", "publication_id"} <= _columns(db_session, "catalog_active_vector_spaces").keys()
    embedding_columns = _columns(db_session, "catalog_search_embeddings")
    assert embedding_columns["embedding"] == "vector"
    embedding_constraints = _constraint_definitions(db_session, "catalog_search_embeddings")
    assert all(value in embedding_constraints for value in ("publication_id", "name_id", "vector_space_id"))
    embedding_indexes = _index_definitions(db_session, "catalog_search_embeddings")
    assert "vector_cosine_ops" in embedding_indexes and "WHERE" in embedding_indexes

    name_indexes = _index_definitions(db_session, "catalog_search_names")
    assert "gist_trgm_ops" in name_indexes

    relation_constraints = _constraint_definitions(db_session, "catalog_search_relation_evidence")
    assert all(value in relation_constraints for value in ("name_variant", "regional_preparation_variant", "same_category_food", "active", "revoked"))
    relation_columns = _columns(db_session, "catalog_search_relation_evidence")
    assert {"source_name_id", "target_name_id", "relation", "status", "command_key", "occurred_at"} <= relation_columns.keys()

    job_columns = _columns(db_session, "catalog_embedding_jobs")
    assert {"publication_id", "name_id", "vector_space_id", "attempt_count", "max_attempts", "not_before", "lease_owner", "lease_expires_at"} <= job_columns.keys()
    job_constraints = _constraint_definitions(db_session, "catalog_embedding_jobs")
    assert "attempt_count >= 0" in job_constraints and "max_attempts > 0" in job_constraints
    assert all(value in job_constraints for value in ("publication_id", "name_id", "vector_space_id"))
    assert "WHERE" in _index_definitions(db_session, "catalog_embedding_jobs")

    build_columns = _columns(db_session, "catalog_vector_space_builds")
    assert {"vector_space_id", "requested_by", "reason", "command_key", "snapshot_manifest", "snapshot_hash", "expected_name_count"} <= build_columns.keys()
    completion_columns = _columns(db_session, "catalog_vector_space_build_completions")
    assert {"build_id", "completed_at", "completed_name_count", "completion_hash"} <= completion_columns.keys()
    completion_constraints = _constraint_definitions(db_session, "catalog_vector_space_build_completions")
    assert "UNIQUE (build_id)" in completion_constraints

    approval_columns = _columns(db_session, "catalog_vector_space_activation_approvals")
    assert {"build_id", "release_hash", "dataset_hash", "code_hash", "retrieval_hash", "embedding_hash", "approver_identifier", "approved_at"} <= approval_columns.keys()
    retry_columns = _columns(db_session, "catalog_embedding_retry_commands")
    assert {"publication_id", "name_id", "vector_space_id", "actor_identifier", "reason", "command_key"} <= retry_columns.keys()
