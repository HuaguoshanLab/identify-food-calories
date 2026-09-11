"""PostgreSQL adapter for the versioned hybrid food-search boundary.

The adapter deliberately reads only current, eligible catalog publications.  Search
indexes are derived data, so neither an old vector nor a stale relation assertion
can make a publication usable after its authoritative lifecycle changes.
"""

from __future__ import annotations

import math
import uuid
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import Select, String, bindparam, case, cast, desc, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session, aliased

from app.admin.models import CatalogPublication
from app.nutrition.repository import ADMIN_PUBLICATION_VERSION, SqlAlchemyNutritionRepository
from app.nutrition.schemas import FoodRelation, FoodSearchEvidence, QualifiedFood
from app.nutrition.search_models import (
    CatalogActiveVectorSpace,
    CatalogEmbeddingJob,
    CatalogSearchEmbedding,
    CatalogSearchName,
    CatalogSearchRelationEvidence,
    CatalogSearchVersion,
    CatalogVectorSpace,
    CatalogVectorSpaceBuild,
    CatalogVectorSpaceBuildCompletion,
)
from app.admin.models import CatalogPublicationEligibility


_TEXT_MIN_SIMILARITY = Decimal("0.20")
_VECTOR_DIMENSION = 1024


class SqlAlchemyHybridFoodSearchRepository:
    """Authoritative three-channel adapter; callers still own PASS/ASK semantics."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_current_qualified_exact(self, *, normalized_query: str) -> list[QualifiedFood]:
        statement = (
            self._current_qualified_statement()
            .join(CatalogSearchName, CatalogSearchName.publication_id == CatalogPublication.id)
            .where(CatalogSearchName.normalized_name == bindparam("normalized_query", normalized_query))
            .order_by(CatalogPublication.id)
        )
        return [SqlAlchemyNutritionRepository._to_published_food(row) for row in self._session.scalars(statement).unique()]

    def find_text_candidates(self, *, normalized_query: str, limit: int) -> list[FoodSearchEvidence]:
        if limit <= 0:
            return []
        similarity = func.similarity(
            CatalogSearchName.normalized_name,
            bindparam("normalized_query", normalized_query),
        )
        relation = self._current_relation_for_text_query(normalized_query)
        statement = (
            self._current_qualified_statement()
            .join(CatalogSearchName, CatalogSearchName.publication_id == CatalogPublication.id)
            .add_columns(CatalogSearchName, similarity.label("score"), relation.label("relation"))
            .where(similarity >= _TEXT_MIN_SIMILARITY)
            .order_by(desc(similarity), CatalogSearchName.normalized_name, CatalogPublication.id)
            .limit(limit)
        )
        return [
            FoodSearchEvidence(
                food=SqlAlchemyNutritionRepository._to_published_food(publication),
                relation=self._relation_or_conservative_default(relation_value),
                text_rank=rank,
                text_score=Decimal(str(score)),
            )
            for rank, (publication, _name, score, relation_value) in enumerate(self._session.execute(statement), start=1)
        ]

    def find_vector_candidates(
        self, *, query_vector: tuple[float, ...], limit: int
    ) -> list[FoodSearchEvidence]:
        if limit <= 0:
            return []
        if len(query_vector) != _VECTOR_DIMENSION or not all(math.isfinite(value) for value in query_vector):
            raise ValueError("query vector must be a finite 1024-dimension vector")

        distance = CatalogSearchEmbedding.embedding.cosine_distance(list(query_vector))
        statement = (
            self._current_qualified_statement()
            .join(CatalogSearchName, CatalogSearchName.publication_id == CatalogPublication.id)
            .join(CatalogSearchEmbedding, CatalogSearchEmbedding.name_id == CatalogSearchName.id)
            .join(CatalogActiveVectorSpace, CatalogActiveVectorSpace.vector_space_id == CatalogSearchEmbedding.vector_space_id)
            .join(CatalogVectorSpace, CatalogVectorSpace.id == CatalogActiveVectorSpace.vector_space_id)
            .add_columns(CatalogSearchName, distance.label("distance"))
            .where(
                CatalogSearchEmbedding.status == "ready",
                CatalogVectorSpace.embedding_dimension == _VECTOR_DIMENSION,
            )
            .order_by(distance, CatalogSearchName.normalized_name, CatalogPublication.id)
            .limit(limit)
        )
        return [
            FoodSearchEvidence(
                food=SqlAlchemyNutritionRepository._to_published_food(publication),
                relation=FoodRelation.SAME_CLASS,
                vector_rank=rank,
                vector_score=Decimal(str(max(0.0, 1.0 - float(distance_value)))),
            )
            for rank, (publication, _name, distance_value) in enumerate(self._session.execute(statement), start=1)
        ]

    def get_current_qualified_food(
        self, *, food_id: uuid.UUID, catalog_version: str
    ) -> QualifiedFood | None:
        if catalog_version != ADMIN_PUBLICATION_VERSION:
            return None
        publication = self._session.scalar(
            self._current_qualified_statement().where(CatalogPublication.id == food_id)
        )
        return SqlAlchemyNutritionRepository._to_published_food(publication) if publication is not None else None

    def claim_due_build_embedding_job(self, *, due_at, now, lease_owner: str, lease_expires_at, vector_space_id: uuid.UUID | None = None):
        """Lease one due job belonging to an immutable build manifest.

        The JSONB containment predicate is deliberate: publication-triggered active
        space jobs are not build jobs and must not be consumed by this worker.
        """
        manifest_item = func.jsonb_build_array(
            func.jsonb_build_object(
                "publication_id", cast(CatalogEmbeddingJob.publication_id, String),
                "name_id", cast(CatalogEmbeddingJob.name_id, String),
                "search_version_id", cast(CatalogSearchName.search_version_id, String),
            )
        )
        predicates = [
            CatalogEmbeddingJob.status.in_(("pending", "leased")),
            CatalogEmbeddingJob.not_before <= due_at,
            (CatalogEmbeddingJob.status == "pending") | (CatalogEmbeddingJob.lease_expires_at <= now),
            cast(CatalogVectorSpaceBuild.snapshot_manifest, JSONB).op("@>")(manifest_item),
        ]
        if vector_space_id is not None:
            predicates.append(CatalogEmbeddingJob.vector_space_id == vector_space_id)
        job = self._session.scalar(
            select(CatalogEmbeddingJob)
            .join(CatalogSearchName, CatalogSearchName.id == CatalogEmbeddingJob.name_id)
            .join(CatalogVectorSpaceBuild, CatalogVectorSpaceBuild.vector_space_id == CatalogEmbeddingJob.vector_space_id)
            .where(*predicates)
            .order_by(CatalogEmbeddingJob.not_before, CatalogEmbeddingJob.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if job is None:
            return None
        job.status = "leased"
        job.attempt_count += 1
        job.lease_owner = lease_owner
        job.leased_at = now
        job.lease_expires_at = lease_expires_at
        job.updated_at = now
        self._session.flush()
        return job

    def recheck_leased_build_embedding_job(self, *, job_id: uuid.UUID, lease_owner: str, now) -> str | None:
        """Lock and revalidate authority immediately before provider I/O."""
        context = self._locked_build_job_context(job_id=job_id, lease_owner=lease_owner)
        if context is None:
            return None
        job, name, publication, build = context
        if not self._is_live_build_member(job=job, name=name, publication=publication, build=build):
            self._cancel_stale_job(job, now)
            return None
        return name.normalized_name

    def complete_leased_build_embedding_job(self, *, job_id: uuid.UUID, lease_owner: str, vector: tuple[float, ...], now) -> bool:
        """Upsert only after a second authority check, then reconcile exact coverage."""
        if len(vector) != _VECTOR_DIMENSION or not all(math.isfinite(value) for value in vector):
            raise ValueError("catalog embedding must be a finite 1024-dimension vector")
        context = self._locked_build_job_context(job_id=job_id, lease_owner=lease_owner)
        if context is None:
            return False
        job, name, publication, build = context
        if not self._is_live_build_member(job=job, name=name, publication=publication, build=build):
            self._cancel_stale_job(job, now)
            return False
        embedding = self._session.scalar(
            select(CatalogSearchEmbedding)
            .where(
                CatalogSearchEmbedding.publication_id == job.publication_id,
                CatalogSearchEmbedding.name_id == job.name_id,
                CatalogSearchEmbedding.vector_space_id == job.vector_space_id,
            )
            .with_for_update()
        )
        if embedding is None:
            embedding = CatalogSearchEmbedding(
                id=uuid.uuid4(), publication_id=job.publication_id, name_id=job.name_id,
                vector_space_id=job.vector_space_id, embedding=list(vector), status="ready", created_at=now,
            )
            self._session.add(embedding)
        job.status = "completed"
        job.lease_owner = None
        job.lease_expires_at = None
        job.last_error_code = None
        job.updated_at = now
        self._session.flush()
        self.reconcile_vector_space_build_completions(vector_space_id=build.vector_space_id, now=now)
        return True

    def reconcile_vector_space_build_completions(self, *, vector_space_id: uuid.UUID, now) -> None:
        """Reconcile every immutable manifest for a reusable vector space.

        A later snapshot can reuse already-ready embeddings, so it may have no
        future write-back event of its own.  Rechecking all manifests keeps the
        separate completion evidence complete without issuing Provider work.
        """

        builds = self._session.scalars(
            select(CatalogVectorSpaceBuild)
            .where(CatalogVectorSpaceBuild.vector_space_id == vector_space_id)
            .order_by(CatalogVectorSpaceBuild.requested_at, CatalogVectorSpaceBuild.id)
        ).all()
        for build in builds:
            self._reconcile_build_completion(build=build, now=now)

    def fail_leased_build_embedding_job(self, *, job_id: uuid.UUID, lease_owner: str, error_code: str, retryable: bool, now, max_backoff_seconds: int) -> bool:
        context = self._locked_build_job_context(job_id=job_id, lease_owner=lease_owner)
        if context is None:
            return False
        job, _name, _publication, _build = context
        job.last_error_code = error_code[:80]
        job.lease_owner = None
        job.lease_expires_at = None
        if retryable and job.attempt_count < job.max_attempts:
            job.status = "pending"
            job.not_before = now + timedelta(seconds=min(max_backoff_seconds, 2 ** job.attempt_count))
            retrying = True
        else:
            job.status = "failed"
            retrying = False
        job.updated_at = now
        self._session.flush()
        return retrying

    def _locked_build_job_context(self, *, job_id: uuid.UUID, lease_owner: str):
        manifest_item = func.jsonb_build_array(
            func.jsonb_build_object(
                "publication_id", cast(CatalogEmbeddingJob.publication_id, String),
                "name_id", cast(CatalogEmbeddingJob.name_id, String),
                "search_version_id", cast(CatalogSearchName.search_version_id, String),
            )
        )
        row = self._session.execute(
            select(CatalogEmbeddingJob, CatalogSearchName, CatalogPublication, CatalogVectorSpaceBuild)
            .join(CatalogSearchName, CatalogSearchName.id == CatalogEmbeddingJob.name_id)
            .join(CatalogPublication, CatalogPublication.id == CatalogEmbeddingJob.publication_id)
            .join(CatalogVectorSpaceBuild, CatalogVectorSpaceBuild.vector_space_id == CatalogEmbeddingJob.vector_space_id)
            .where(
                CatalogEmbeddingJob.id == job_id,
                CatalogEmbeddingJob.status == "leased",
                CatalogEmbeddingJob.lease_owner == lease_owner,
                cast(CatalogVectorSpaceBuild.snapshot_manifest, JSONB).op("@>")(manifest_item),
            )
            .with_for_update()
        ).first()
        return row

    def _is_live_build_member(self, *, job, name, publication, build) -> bool:
        manifest_items = {
            (item["publication_id"], item["name_id"], item["search_version_id"])
            for item in build.snapshot_manifest
        }
        if (str(job.publication_id), str(job.name_id), str(name.search_version_id)) not in manifest_items:
            return False
        current_hash = self._session.scalar(
            select(CatalogSearchVersion.content_hash).where(
                CatalogSearchVersion.id == name.search_version_id,
                CatalogSearchVersion.publication_id == publication.id,
            )
        )
        return (
            name.publication_id == publication.id
            and current_hash == publication.content_hash
            and self._latest_eligibility_status(job.publication_id) == "eligible"
        )

    def _latest_eligibility_status(self, publication_id: uuid.UUID) -> str | None:
        return self._session.scalar(
            select(CatalogPublicationEligibility.status)
            .where(CatalogPublicationEligibility.publication_id == publication_id)
            .order_by(CatalogPublicationEligibility.occurred_at.desc(), CatalogPublicationEligibility.id.desc())
            .limit(1)
        )

    @staticmethod
    def _cancel_stale_job(job, now) -> None:
        job.status = "failed"
        job.attempt_count = job.max_attempts
        job.lease_owner = None
        job.lease_expires_at = None
        job.last_error_code = "stale_authority"
        job.updated_at = now

    def _reconcile_build_completion(self, *, build, now) -> None:
        # Lock the immutable build while proving its exact manifest coverage.  This
        # serializes two final job write-backs without granting either activation.
        build = self._session.scalar(
            select(CatalogVectorSpaceBuild)
            .where(CatalogVectorSpaceBuild.id == build.id)
            .with_for_update()
        )
        if build is None:  # pragma: no cover - FK integrity protects this in PostgreSQL
            return
        manifest = build.snapshot_manifest
        expected = {(item["publication_id"], item["name_id"]) for item in manifest}
        name_ids = [uuid.UUID(item["name_id"]) for item in manifest]
        # A vector-space identity is reusable.  Completion proves this immutable
        # manifest only, so embeddings from another complete snapshot must not
        # make equality fail or prevent its independent evidence record.
        rows = self._session.execute(
            select(CatalogSearchEmbedding.publication_id, CatalogSearchEmbedding.name_id)
            .where(
                CatalogSearchEmbedding.vector_space_id == build.vector_space_id,
                CatalogSearchEmbedding.status == "ready",
                CatalogSearchEmbedding.name_id.in_(name_ids),
            )
        ).all()
        actual = {(str(publication_id), str(name_id)) for publication_id, name_id in rows}
        if len(manifest) != build.expected_name_count or actual != expected:
            return
        completion = self._session.scalar(
            select(CatalogVectorSpaceBuildCompletion)
            .where(CatalogVectorSpaceBuildCompletion.build_id == build.id)
            .with_for_update()
        )
        if completion is None:
            from app.nutrition.index_worker import completion_hash
            self._session.add(CatalogVectorSpaceBuildCompletion(
                id=uuid.uuid4(), build_id=build.id, completed_name_count=len(actual),
                completion_hash=completion_hash(snapshot_hash=build.snapshot_hash, manifest=manifest), completed_at=now,
            ))
            self._session.flush()

    @staticmethod
    def _current_qualified_statement() -> Select[tuple[CatalogPublication]]:
        """One live authority predicate shared by all channels and confirmation."""
        return SqlAlchemyNutritionRepository.current_qualified_publication_statement()

    def _current_relation_for_text_query(self, normalized_query: str):
        """Use relation evidence only when both endpoints are current content versions."""

        source_name = aliased(CatalogSearchName)
        source_publication = aliased(CatalogPublication)
        source_version = aliased(CatalogSearchVersion)
        target_version = aliased(CatalogSearchVersion)
        source_current = self._current_qualified_statement().with_only_columns(CatalogPublication.id).subquery()
        target_current = self._current_qualified_statement().with_only_columns(CatalogPublication.id).subquery()
        return (
            select(CatalogSearchRelationEvidence.relation)
            .join(source_name, source_name.id == CatalogSearchRelationEvidence.source_name_id)
            .join(source_publication, source_publication.id == source_name.publication_id)
            .join(source_version, source_version.id == source_name.search_version_id)
            .join(target_version, target_version.id == CatalogSearchName.search_version_id)
            .where(
                CatalogSearchRelationEvidence.target_name_id == CatalogSearchName.id,
                CatalogSearchRelationEvidence.status == "active",
                source_name.normalized_name == bindparam("relation_query", normalized_query),
                source_publication.id.in_(select(source_current.c.id)),
                CatalogSearchName.publication_id.in_(select(target_current.c.id)),
                source_version.content_hash == source_publication.content_hash,
                target_version.content_hash == CatalogPublication.content_hash,
            )
            .order_by(
                case(
                    (CatalogSearchRelationEvidence.relation == "name_variant", 0),
                    (CatalogSearchRelationEvidence.relation == "regional_preparation_variant", 1),
                    else_=2,
                ),
                CatalogSearchRelationEvidence.occurred_at.desc(),
            )
            .limit(1)
            .scalar_subquery()
        )

    @staticmethod
    def _relation_or_conservative_default(value: str | None) -> FoodRelation:
        return {
            "name_variant": FoodRelation.NAME_VARIANT,
            "regional_preparation_variant": FoodRelation.REGIONAL_PREPARATION_VARIANT,
            "same_category_food": FoodRelation.SAME_CLASS,
        }.get(value, FoodRelation.SAME_CLASS)
