"""Real PostgreSQL contracts for versioned hybrid catalog retrieval."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import uuid

from sqlalchemy import select, text

from app.admin.models import CatalogPublication
from app.admin.repository import SqlAlchemyAdminRepository
from app.admin.schemas import CatalogDraftCreateCommand, CatalogLifecycleCommand
from app.admin.service import AdminService
from app.auth.models import User, UserRole
from app.nutrition.repository import ADMIN_PUBLICATION_VERSION
from app.nutrition.search_models import (
    CatalogActiveVectorSpace,
    CatalogSearchEmbedding,
    CatalogSearchName,
    CatalogSearchVersion,
)


def _publish(db_session, *, canonical_name: str, aliases: list[str]) -> CatalogPublication:
    now = datetime.now(UTC)
    actor = User(
        id=uuid.uuid4(), email=f"hybrid-{uuid.uuid4().hex}@example.test", password_hash="hash",
        role=UserRole.ADMIN.value, is_active=True, email_verified_at=now, created_at=now, updated_at=now,
    )
    db_session.add(actor)
    db_session.flush()
    service = AdminService(
        repository=SqlAlchemyAdminRepository(db_session), now=lambda: now,
        commit=db_session.commit, rollback=db_session.rollback,
    )
    draft = service.create_catalog_draft(
        actor_user_id=actor.id,
        command=CatalogDraftCreateCommand(
            canonical_name=canonical_name, aliases=aliases,
            energy_kcal_per_100g=Decimal("116"), protein_g_per_100g=Decimal("2.6"),
            fat_g_per_100g=Decimal("0.3"), carbohydrate_g_per_100g=Decimal("25.9"),
            source_name="USDA", source_url="https://fdc.nal.usda.gov/",
            authorization_status="authorized", reason="hybrid retrieval fixture",
        ),
        command_key=f"hybrid-create-{uuid.uuid4().hex}",
    )
    command = CatalogLifecycleCommand(reason="fixture approved", confirm=True)
    service.review_catalog_draft(actor_user_id=actor.id, draft_id=draft.id, expected_revision=1, command=command, command_key=f"hybrid-review-{uuid.uuid4().hex}")
    publication = service.publish_catalog_draft(actor_user_id=actor.id, draft_id=draft.id, expected_revision=1, command=command, command_key=f"hybrid-publish-{uuid.uuid4().hex}")
    return db_session.scalar(select(CatalogPublication).where(CatalogPublication.id == publication.id))


def _index_name(db_session, publication: CatalogPublication, normalized_name: str) -> CatalogSearchName:
    now = datetime.now(UTC)
    version = db_session.scalar(
        select(CatalogSearchVersion).where(
            CatalogSearchVersion.publication_id == publication.id,
            CatalogSearchVersion.content_hash == publication.content_hash,
        )
    )
    if version is None:
        version = CatalogSearchVersion(
            publication_id=publication.id, content_hash=publication.content_hash, created_at=now,
        )
        db_session.add(version)
        db_session.flush()
    name = db_session.scalar(
        select(CatalogSearchName).where(
            CatalogSearchName.publication_id == publication.id,
            CatalogSearchName.normalized_name == normalized_name,
        )
    )
    if name is None:
        name = CatalogSearchName(
            publication_id=publication.id, search_version_id=version.id,
            display_name=normalized_name, normalized_name=normalized_name,
            name_kind="canonical", created_at=now,
        )
        db_session.add(name)
        db_session.flush()
    return name


def test_hybrid_search_repository_exposes_an_authoritative_adapter() -> None:
    """Plan 06 owns the real-PostgreSQL retrieval adapter, not a service-side fallback."""

    from app.nutrition.search_repository import SqlAlchemyHybridFoodSearchRepository

    assert SqlAlchemyHybridFoodSearchRepository.__name__ == "SqlAlchemyHybridFoodSearchRepository"


def test_exact_and_confirmation_reread_use_current_qualified_publication(db_session) -> None:
    from app.nutrition.search_repository import SqlAlchemyHybridFoodSearchRepository

    publication = _publish(db_session, canonical_name="米饭", aliases=["白米饭"])
    _index_name(db_session, publication, "米饭")
    repository = SqlAlchemyHybridFoodSearchRepository(db_session)

    assert [food.id for food in repository.find_current_qualified_exact(normalized_query="米饭")] == [publication.id]
    assert repository.get_current_qualified_food(food_id=publication.id, catalog_version=ADMIN_PUBLICATION_VERSION) is not None
    assert repository.get_current_qualified_food(food_id=publication.id, catalog_version="stale") is None


def test_text_and_vector_candidates_only_read_current_eligible_index_rows(db_session) -> None:
    from app.nutrition.search_repository import SqlAlchemyHybridFoodSearchRepository

    name_value = f"番茄炒蛋-{uuid.uuid4().hex}"
    publication = _publish(db_session, canonical_name=name_value, aliases=["西红柿炒鸡蛋"])
    name = _index_name(db_session, publication, name_value)
    active_space = db_session.scalar(
        select(CatalogActiveVectorSpace).where(CatalogActiveVectorSpace.pointer_key == "catalog")
    )
    assert active_space is not None
    db_session.add(CatalogSearchEmbedding(
        publication_id=publication.id, name_id=name.id, vector_space_id=active_space.vector_space_id,
        embedding=[1.0, *([0.0] * 1023)], status="ready", created_at=datetime.now(UTC),
    ))
    db_session.flush()

    repository = SqlAlchemyHybridFoodSearchRepository(db_session)
    text_candidates = repository.find_text_candidates(normalized_query=name_value, limit=3)
    vector_candidates = repository.find_vector_candidates(query_vector=tuple([1.0, *([0.0] * 1023)]), limit=3)

    assert publication.id in {candidate.food.id for candidate in text_candidates}
    assert publication.id in {candidate.food.id for candidate in vector_candidates}
    assert [candidate.text_rank for candidate in text_candidates] == list(range(1, len(text_candidates) + 1))
    assert [candidate.vector_rank for candidate in vector_candidates] == list(range(1, len(vector_candidates) + 1))


def test_text_fixture_has_captured_bounded_postgresql_explain_evidence(db_session) -> None:
    """Keep query-plan evidence in the real database gate, not an ORM-only assertion."""

    plan = db_session.scalars(
        text(
            "EXPLAIN (ANALYZE, BUFFERS) "
            "SELECT id FROM catalog_search_names "
            "WHERE normalized_name = :normalized_name ORDER BY id LIMIT 3"
        ),
        {"normalized_name": "番茄炒蛋"},
    ).all()

    assert plan and any("Limit" in line for line in plan)


def _columns(db_session, table_name: str) -> dict[str, str]:
    rows = db_session.execute(
        text(
            "SELECT column_name, udt_name "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :table_name"
        ),
        {"table_name": table_name},
    )
    return dict(rows.all())


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
    assert {"id", "embedding_model", "embedding_dimension", "adapter_version", "retrieval_version"} <= space_columns.keys()
    space_constraints = _constraint_definitions(db_session, "catalog_vector_spaces")
    assert "embedding_dimension = 1024" in space_constraints
    assert "embedding_model" in space_constraints and "adapter_version" in space_constraints and "retrieval_version" in space_constraints
    assert "UNIQUE (embedding_model, embedding_dimension, adapter_version, retrieval_version)" in space_constraints

    active_columns = _columns(db_session, "catalog_active_vector_spaces")
    assert {"pointer_key", "vector_space_id", "advanced_at"} <= active_columns.keys()
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
    assert {"vector_space_id", "requested_by", "reason", "command_key", "retrieval_version", "snapshot_manifest", "snapshot_hash", "expected_name_count"} <= build_columns.keys()
    completion_columns = _columns(db_session, "catalog_vector_space_build_completions")
    assert {"build_id", "completed_at", "completed_name_count", "completion_hash"} <= completion_columns.keys()
    completion_constraints = _constraint_definitions(db_session, "catalog_vector_space_build_completions")
    assert "UNIQUE (build_id)" in completion_constraints

    approval_columns = _columns(db_session, "catalog_vector_space_activation_approvals")
    assert {"build_id", "release_hash", "dataset_hash", "code_hash", "retrieval_hash", "embedding_hash", "approver_identifier", "approved_at"} <= approval_columns.keys()
    retry_columns = _columns(db_session, "catalog_embedding_retry_commands")
    assert {"publication_id", "name_id", "vector_space_id", "actor_identifier", "reason", "command_key"} <= retry_columns.keys()
