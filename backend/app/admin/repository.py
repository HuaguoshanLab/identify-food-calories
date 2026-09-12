"""SQLAlchemy adapter for admin role reads, locks, and audit insertion."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import and_, case, exists, func, or_, select, text
from sqlalchemy.orm import Session, aliased

from app.admin.models import (
    AdminAuditEvent,
    AdminRoleAudit,
    CatalogActivePublication,
    CatalogDraft,
    CatalogDraftChangeSet,
    CatalogDraftReview,
    CatalogDraftRevision,
    CatalogPublication,
    CatalogPublicationEligibility,
)
from app.agent.models import AgentInvocation, AgentRun, AgentRuntimeConfigVersion
from app.admin.schemas import AdminRunMetricsResponse, AdminUserQuery, CatalogListQuery
from app.admin.ports import QualifiedRecipeFoodReference
from app.auth.models import User, UserRole
from app.nutrition.models import FoodCatalogItem, NutritionCatalogVersion
from app.planning.models import ManagedRecipeCandidate
from app.nutrition.search_models import (
    CatalogActiveVectorSpace,
    CatalogEmbeddingJob,
    CatalogSearchEmbedding,
    CatalogSearchRelationEvidence,
    CatalogSearchName,
    CatalogSearchVersion,
    CatalogVectorSpace,
    CatalogVectorSpaceBuild,
    CatalogVectorSpaceBuildCompletion,
    CatalogVectorSpaceActivationApproval,
)


class SqlAlchemyAdminRepository:
    """Flush-only persistence adapter; the service owns the transaction boundary."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def acquire_bootstrap_lock(self) -> None:
        """Serialize the one-time bootstrap check without adding mutable global state."""

        self._session.execute(text("SELECT pg_advisory_xact_lock(918273645)"))

    def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        return self._session.get(User, user_id)

    def get_user_by_email(self, normalized_email: str) -> User | None:
        return self._session.scalar(select(User).where(User.email == normalized_email))

    def get_user_for_update(self, user_id: uuid.UUID) -> User | None:
        return self._session.scalar(
            select(User).where(User.id == user_id).with_for_update()
        )

    def has_active_admin(self) -> bool:
        return bool(
            self._session.scalar(
                select(
                    exists().where(
                        User.role == UserRole.ADMIN.value,
                        User.is_active.is_(True),
                    )
                )
            )
        )

    def count_active_admins(self) -> int:
        return int(self._session.scalar(select(func.count()).select_from(User).where(User.role == UserRole.ADMIN.value, User.is_active.is_(True))) or 0)

    def list_users(self, *, query: AdminUserQuery, limit: int, offset: int) -> tuple[list[User], int]:
        predicates = []
        if query.search:
            escaped = query.search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            predicates.append(User.email.ilike(f"%{escaped}%", escape="\\"))
        if query.role:
            predicates.append(User.role == query.role)
        if query.status == "active":
            predicates.extend((User.is_active.is_(True), User.email_verified_at.is_not(None)))
        elif query.status == "inactive":
            predicates.append(User.is_active.is_(False))
        elif query.status == "unverified":
            predicates.append(User.email_verified_at.is_(None))
        where = and_(*predicates) if predicates else True
        total = int(self._session.scalar(select(func.count()).select_from(User).where(where)) or 0)
        rows = list(self._session.scalars(select(User).where(where).order_by(User.created_at.desc(), User.id.desc()).limit(limit).offset(offset)))
        return rows, total

    def count_users_by_role(self) -> dict[str, int]:
        rows = self._session.execute(select(User.role, func.count()).group_by(User.role)).all()
        return {str(role): int(count) for role, count in rows}

    def add_audit(self, audit: AdminRoleAudit) -> AdminRoleAudit:
        self._session.add(audit)
        self._session.flush()
        return audit

    def add_audit_event(self, event: AdminAuditEvent) -> AdminAuditEvent:
        self._session.add(event)
        self._session.flush()
        return event

    def get_audit_event_by_command_key(
        self, command_key: str
    ) -> AdminAuditEvent | None:
        return self._session.scalar(
            select(AdminAuditEvent).where(AdminAuditEvent.command_key == command_key)
        )

    def acquire_runtime_config_lock(self) -> None:
        """Serialize active-policy selection and version allocation per transaction."""

        self._session.execute(text("SELECT pg_advisory_xact_lock(60516019)"))

    def get_runtime_config_command(
        self, command_key: str
    ) -> AgentRuntimeConfigVersion | None:
        return self._session.scalar(
            select(AgentRuntimeConfigVersion).where(
                AgentRuntimeConfigVersion.command_key == command_key
            )
        )

    def get_active_runtime_config(self) -> AgentRuntimeConfigVersion | None:
        return self._session.scalar(
            select(AgentRuntimeConfigVersion)
            .order_by(AgentRuntimeConfigVersion.version.desc())
            .limit(1)
        )

    def next_runtime_config_version(self) -> int:
        return (
            int(
                self._session.scalar(
                    select(
                        func.coalesce(func.max(AgentRuntimeConfigVersion.version), 0)
                    )
                )
                or 0
            )
            + 1
        )

    def add_runtime_config_version(
        self, version: AgentRuntimeConfigVersion
    ) -> AgentRuntimeConfigVersion:
        self._session.add(version)
        self._session.flush()
        return version

    def list_catalog_drafts(
        self, *, query: CatalogListQuery, limit: int, offset: int
    ) -> tuple[list[CatalogDraft], int]:
        # Escape LIKE metacharacters: a user searching for '%' expects literal data.
        predicates = []
        if query.search:
            # Decode JSON array elements before matching; serialized Unicode escapes
            # would make a text cast silently miss Chinese aliases.
            aliases = (
                func.json_array_elements_text(CatalogDraft.aliases)
                .table_valued("value")
                .alias("catalog_alias")
            )
            predicates.append(
                or_(
                    CatalogDraft.canonical_name.icontains(
                        query.search, autoescape=True
                    ),
                    exists(
                        select(1)
                        .select_from(aliases)
                        .where(aliases.c.value.icontains(query.search, autoescape=True))
                    ),
                )
            )
        if query.source:
            predicates.append(
                CatalogDraft.source_name.icontains(query.source, autoescape=True)
            )
        if query.authorization_status is not None:
            predicates.append(
                CatalogDraft.authorization_status == query.authorization_status
            )
        total = (
            self._session.scalar(
                select(func.count()).select_from(CatalogDraft).where(*predicates)
            )
            or 0
        )
        items = self._session.scalars(
            select(CatalogDraft)
            .where(*predicates)
            .order_by(CatalogDraft.created_at.desc(), CatalogDraft.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        return list(items), int(total)

    def acquire_catalog_import_lock(self, command_key: str) -> None:
        self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
            {"key": f"catalog-import:{command_key}"},
        )

    def get_catalog_draft(
        self, draft_id: uuid.UUID, *, for_update: bool = False
    ) -> CatalogDraft | None:
        statement = select(CatalogDraft).where(CatalogDraft.id == draft_id)
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def get_catalog_draft_command(
        self, command_key: str
    ) -> CatalogDraftChangeSet | None:
        return self._session.scalar(
            select(CatalogDraftChangeSet).where(
                CatalogDraftChangeSet.command_key == command_key
            )
        )

    def add_catalog_draft(self, draft: CatalogDraft) -> CatalogDraft:
        self._session.add(draft)
        self._session.flush()
        return draft

    def add_catalog_draft_change_set(
        self, change_set: CatalogDraftChangeSet
    ) -> CatalogDraftChangeSet:
        self._session.add(change_set)
        self._session.flush()
        return change_set

    def add_catalog_draft_revision(
        self, revision: CatalogDraftRevision
    ) -> CatalogDraftRevision:
        self._session.add(revision)
        self._session.flush()
        return revision

    def acquire_catalog_publication_lock(self, draft_id: uuid.UUID) -> None:
        # Transaction-scoped advisory locking serializes publication even before a
        # pointer row exists, closing the first-publish race without global locks.
        self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:draft_id))"),
            {"draft_id": str(draft_id)},
        )

    def get_catalog_review(
        self, *, draft_id: uuid.UUID, revision: int
    ) -> CatalogDraftReview | None:
        return self._session.scalar(
            select(CatalogDraftReview).where(
                CatalogDraftReview.draft_id == draft_id,
                CatalogDraftReview.draft_revision == revision,
            )
        )

    def add_catalog_review(self, review: CatalogDraftReview) -> CatalogDraftReview:
        self._session.add(review)
        self._session.flush()
        return review

    def get_catalog_publication_command(
        self, command_key: str
    ) -> CatalogPublication | None:
        return self._session.scalar(
            select(CatalogPublication).where(
                CatalogPublication.command_key == command_key
            )
        )

    def add_catalog_publication(
        self, publication: CatalogPublication
    ) -> CatalogPublication:
        self._session.add(publication)
        self._session.flush()
        return publication

    def get_active_catalog_publication(
        self, draft_id: uuid.UUID
    ) -> CatalogPublication | None:
        return self._session.scalar(
            select(CatalogPublication)
            .join(
                CatalogActivePublication,
                CatalogActivePublication.publication_id == CatalogPublication.id,
            )
            .where(CatalogActivePublication.draft_id == draft_id)
        )

    def advance_active_catalog_publication(
        self, *, draft_id: uuid.UUID, publication_id: uuid.UUID
    ) -> CatalogActivePublication:
        pointer = self._session.get(CatalogActivePublication, draft_id)
        if pointer is None:
            pointer = CatalogActivePublication(
                draft_id=draft_id,
                publication_id=publication_id,
                advanced_at=datetime.now().astimezone(),
            )
            self._session.add(pointer)
        else:
            pointer.publication_id = publication_id
            pointer.advanced_at = datetime.now().astimezone()
        self._session.flush()
        return pointer

    def get_catalog_publication(
        self, publication_id: uuid.UUID
    ) -> CatalogPublication | None:
        return self._session.get(CatalogPublication, publication_id)

    def get_catalog_eligibility_command(
        self, command_key: str
    ) -> CatalogPublicationEligibility | None:
        return self._session.scalar(
            select(CatalogPublicationEligibility).where(
                CatalogPublicationEligibility.command_key == command_key
            )
        )

    def get_latest_catalog_eligibility(
        self, publication_id: uuid.UUID
    ) -> CatalogPublicationEligibility | None:
        return self._session.scalar(
            select(CatalogPublicationEligibility)
            .where(CatalogPublicationEligibility.publication_id == publication_id)
            .order_by(
                CatalogPublicationEligibility.occurred_at.desc(),
                CatalogPublicationEligibility.id.desc(),
            )
            .limit(1)
        )

    def add_catalog_eligibility(
        self, eligibility: CatalogPublicationEligibility
    ) -> CatalogPublicationEligibility:
        self._session.add(eligibility)
        self._session.flush()
        return eligibility

    def list_active_catalog_vector_spaces(self) -> list[CatalogVectorSpace]:
        return list(
            self._session.scalars(
                select(CatalogVectorSpace)
                .join(
                    CatalogActiveVectorSpace,
                    CatalogActiveVectorSpace.vector_space_id == CatalogVectorSpace.id,
                )
                .order_by(CatalogVectorSpace.id)
            )
        )

    def acquire_catalog_search_index_backfill_lock(self) -> None:
        self._session.execute(text("SELECT pg_advisory_xact_lock(63021023)"))

    def list_current_qualified_catalog_publications(self) -> list[CatalogPublication]:
        from app.nutrition.repository import SqlAlchemyNutritionRepository
        return list(self._session.scalars(
            SqlAlchemyNutritionRepository.current_qualified_publication_statement().order_by(CatalogPublication.id)
        ))

    def get_catalog_search_version(self, *, publication_id: uuid.UUID, content_hash: str) -> CatalogSearchVersion | None:
        return self._session.scalar(select(CatalogSearchVersion).where(
            CatalogSearchVersion.publication_id == publication_id,
            CatalogSearchVersion.content_hash == content_hash,
        ))

    def add_catalog_search_version(
        self, version: CatalogSearchVersion
    ) -> CatalogSearchVersion:
        self._session.add(version)
        self._session.flush()
        return version

    def add_catalog_search_names(
        self, names: list[CatalogSearchName]
    ) -> list[CatalogSearchName]:
        self._session.add_all(names)
        self._session.flush()
        return names

    def list_catalog_search_names_for_publication(self, publication_id: uuid.UUID) -> list[CatalogSearchName]:
        return list(self._session.scalars(select(CatalogSearchName).where(CatalogSearchName.publication_id == publication_id)))

    def add_catalog_embedding_jobs(
        self, jobs: list[CatalogEmbeddingJob]
    ) -> list[CatalogEmbeddingJob]:
        self._session.add_all(jobs)
        self._session.flush()
        return jobs

    def list_catalog_embedding_jobs(
        self, publication_id: uuid.UUID, *, for_update: bool = False
    ) -> list[CatalogEmbeddingJob]:
        statement = (
            select(CatalogEmbeddingJob)
            .where(CatalogEmbeddingJob.publication_id == publication_id)
            .order_by(CatalogEmbeddingJob.id)
        )
        if for_update:
            statement = statement.with_for_update()
        return list(self._session.scalars(statement))

    def acquire_catalog_vector_space_build_lock(self) -> None:
        self._session.execute(text("SELECT pg_advisory_xact_lock(63021021)"))

    def get_catalog_vector_space(self, *, embedding_model: str, embedding_dimension: int, adapter_version: str, retrieval_version: str) -> CatalogVectorSpace | None:
        return self._session.scalar(select(CatalogVectorSpace).where(
            CatalogVectorSpace.embedding_model == embedding_model,
            CatalogVectorSpace.embedding_dimension == embedding_dimension,
            CatalogVectorSpace.adapter_version == adapter_version,
            CatalogVectorSpace.retrieval_version == retrieval_version,
        ))

    def get_catalog_vector_space_by_id(self, vector_space_id: uuid.UUID) -> CatalogVectorSpace | None:
        return self._session.get(CatalogVectorSpace, vector_space_id)

    def add_catalog_vector_space(self, space: CatalogVectorSpace) -> CatalogVectorSpace:
        self._session.add(space)
        self._session.flush()
        return space

    def list_current_eligible_catalog_search_names(self) -> list[CatalogSearchName]:
        latest_status = (
            select(CatalogPublicationEligibility.status)
            .where(CatalogPublicationEligibility.publication_id == CatalogSearchName.publication_id)
            .order_by(CatalogPublicationEligibility.occurred_at.desc(), CatalogPublicationEligibility.id.desc())
            .limit(1).scalar_subquery()
        )
        return list(self._session.scalars(
            select(CatalogSearchName)
            .join(CatalogSearchVersion, CatalogSearchVersion.id == CatalogSearchName.search_version_id)
            .join(CatalogPublication, CatalogPublication.id == CatalogSearchName.publication_id)
            .where(CatalogSearchVersion.content_hash == CatalogPublication.content_hash, latest_status == "eligible")
            .order_by(CatalogSearchName.publication_id, CatalogSearchName.name_kind, CatalogSearchName.normalized_name, CatalogSearchName.id)
        ))

    def get_catalog_vector_space_build_by_command_key(self, command_key: str) -> CatalogVectorSpaceBuild | None:
        return self._session.scalar(select(CatalogVectorSpaceBuild).where(CatalogVectorSpaceBuild.command_key == command_key))

    def add_catalog_vector_space_build(self, build: CatalogVectorSpaceBuild) -> CatalogVectorSpaceBuild:
        self._session.add(build)
        self._session.flush()
        return build

    def list_catalog_vector_space_builds(self) -> list[CatalogVectorSpaceBuild]:
        return list(self._session.scalars(
            select(CatalogVectorSpaceBuild).order_by(
                CatalogVectorSpaceBuild.requested_at.desc(), CatalogVectorSpaceBuild.id.desc()
            )
        ))

    def list_catalog_embedding_jobs_for_vector_space(self, vector_space_id: uuid.UUID, *, name_ids: list[uuid.UUID]) -> list[CatalogEmbeddingJob]:
        if not name_ids:
            return []
        return list(self._session.scalars(select(CatalogEmbeddingJob).where(
            CatalogEmbeddingJob.vector_space_id == vector_space_id,
            CatalogEmbeddingJob.name_id.in_(name_ids),
        ).order_by(CatalogEmbeddingJob.id)))

    def acquire_catalog_vector_space_activation_lock(self) -> None:
        """Serialize pointer creation and switching before taking row locks."""

        self._session.execute(text("SELECT pg_advisory_xact_lock(63021022)"))

    def get_catalog_vector_space_activation_approval(self, command_key: str) -> CatalogVectorSpaceActivationApproval | None:
        return self._session.scalar(
            select(CatalogVectorSpaceActivationApproval)
            .where(CatalogVectorSpaceActivationApproval.command_key == command_key)
            .with_for_update()
        )

    def list_catalog_vector_space_builds_for_activation(self, vector_space_id: uuid.UUID) -> list[CatalogVectorSpaceBuild]:
        return list(self._session.scalars(
            select(CatalogVectorSpaceBuild)
            .where(CatalogVectorSpaceBuild.vector_space_id == vector_space_id)
            .order_by(CatalogVectorSpaceBuild.requested_at, CatalogVectorSpaceBuild.id)
            .with_for_update()
        ))

    def get_catalog_vector_space_build_for_activation(self, build_id: uuid.UUID) -> CatalogVectorSpaceBuild | None:
        return self._session.scalar(
            select(CatalogVectorSpaceBuild)
            .where(CatalogVectorSpaceBuild.id == build_id)
            .with_for_update()
        )

    def get_catalog_vector_space_build_completion(self, build_id: uuid.UUID) -> CatalogVectorSpaceBuildCompletion | None:
        return self._session.scalar(
            select(CatalogVectorSpaceBuildCompletion)
            .where(CatalogVectorSpaceBuildCompletion.build_id == build_id)
            .with_for_update()
        )

    def list_catalog_search_embeddings_for_vector_space(self, vector_space_id: uuid.UUID, *, name_ids: list[uuid.UUID]) -> list[CatalogSearchEmbedding]:
        if not name_ids:
            return []
        return list(self._session.scalars(
            select(CatalogSearchEmbedding)
            .where(CatalogSearchEmbedding.vector_space_id == vector_space_id, CatalogSearchEmbedding.name_id.in_(name_ids))
            .with_for_update()
        ))

    def get_active_catalog_vector_space_for_update(self) -> CatalogActiveVectorSpace | None:
        return self._session.scalar(
            select(CatalogActiveVectorSpace)
            .where(CatalogActiveVectorSpace.pointer_key == "catalog")
            .with_for_update()
        )

    def activate_catalog_vector_space(
        self, *, approval: CatalogVectorSpaceActivationApproval, vector_space_id: uuid.UUID, now: datetime
    ) -> CatalogActiveVectorSpace:
        """Persist approval first, then change the sole mutable pointer in this transaction."""

        self._session.add(approval)
        self._session.flush()
        pointer = self.get_active_catalog_vector_space_for_update()
        if pointer is None:
            pointer = CatalogActiveVectorSpace(pointer_key="catalog", vector_space_id=vector_space_id, advanced_at=now)
            self._session.add(pointer)
        else:
            pointer.vector_space_id = vector_space_id
            pointer.advanced_at = now
        self._session.flush()
        return pointer

    def reconcile_catalog_vector_space_build_completion(
        self, *, build: CatalogVectorSpaceBuild, now: datetime
    ) -> CatalogVectorSpaceBuildCompletion | None:
        """Write evidence for this exact immutable manifest, even when jobs predate it."""

        locked = self.get_catalog_vector_space_build_for_activation(build.id)
        if locked is None:  # pragma: no cover - protected by the caller's persisted build
            return None
        existing = self.get_catalog_vector_space_build_completion(locked.id)
        if existing is not None:
            return existing
        try:
            expected = {
                (uuid.UUID(item["publication_id"]), uuid.UUID(item["name_id"]))
                for item in locked.snapshot_manifest
            }
        except (KeyError, TypeError, ValueError):
            return None
        if len(expected) != locked.expected_name_count:
            return None
        name_ids = [name_id for _, name_id in expected]
        jobs = self.list_catalog_embedding_jobs_for_vector_space(locked.vector_space_id, name_ids=name_ids)
        embeddings = self.list_catalog_search_embeddings_for_vector_space(locked.vector_space_id, name_ids=name_ids)
        if (
            len(jobs) != locked.expected_name_count
            or len(embeddings) != locked.expected_name_count
            or any(job.status != "completed" for job in jobs)
            or any(embedding.status != "ready" for embedding in embeddings)
            or {(job.publication_id, job.name_id) for job in jobs} != expected
            or {(embedding.publication_id, embedding.name_id) for embedding in embeddings} != expected
        ):
            return None
        from app.nutrition.index_worker import completion_hash

        completion = CatalogVectorSpaceBuildCompletion(
            id=uuid.uuid4(), build_id=locked.id, completed_name_count=len(expected),
            completion_hash=completion_hash(snapshot_hash=locked.snapshot_hash, manifest=locked.snapshot_manifest),
            completed_at=now,
        )
        self._session.add(completion)
        self._session.flush()
        return completion

    def acquire_catalog_embedding_retry_lock(self, publication_id: uuid.UUID) -> None:
        # A publication-scoped transaction lock keeps a replay from resetting a job
        # after a concurrent request already committed its audit outcome.
        self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:publication_id))"),
            {"publication_id": f"embedding-retry:{publication_id}"},
        )

    def get_catalog_search_name_for_publication(
        self, *, name_id: uuid.UUID, publication_id: uuid.UUID
    ) -> CatalogSearchName | None:
        """Accept only a name derived from this immutable publication content version."""

        return self._session.scalar(
            select(CatalogSearchName)
            .join(
                CatalogSearchVersion,
                CatalogSearchVersion.id == CatalogSearchName.search_version_id,
            )
            .join(
                CatalogPublication,
                CatalogPublication.id == CatalogSearchName.publication_id,
            )
            .where(
                CatalogSearchName.id == name_id,
                CatalogSearchName.publication_id == publication_id,
                CatalogSearchVersion.publication_id == publication_id,
                CatalogSearchVersion.content_hash == CatalogPublication.content_hash,
            )
        )

    def get_catalog_search_name(self, name_id: uuid.UUID) -> CatalogSearchName | None:
        return self._session.get(CatalogSearchName, name_id)

    def get_catalog_relation_evidence(
        self, evidence_id: uuid.UUID
    ) -> CatalogSearchRelationEvidence | None:
        return self._session.get(CatalogSearchRelationEvidence, evidence_id)

    def get_catalog_relation_evidence_by_command_key(
        self, command_key: str
    ) -> CatalogSearchRelationEvidence | None:
        return self._session.scalar(
            select(CatalogSearchRelationEvidence).where(
                CatalogSearchRelationEvidence.command_key == command_key
            )
        )

    def add_catalog_relation_evidence(
        self, evidence: CatalogSearchRelationEvidence
    ) -> CatalogSearchRelationEvidence:
        self._session.add(evidence)
        self._session.flush()
        return evidence

    def list_audit_events(
        self,
        *,
        limit: int,
        cursor_position: tuple[datetime, uuid.UUID] | None,
        action: str | None = None,
        object_type: str | None = None,
        object_id: str | None = None,
        actor_identifier: str | None = None,
        reason: str | None = None,
        occurred_after: datetime | None = None,
        occurred_before: datetime | None = None,
    ) -> list[AdminAuditEvent]:
        """Read a deterministic keyset page without materializing any raw payload."""

        statement = select(AdminAuditEvent)
        if action is not None:
            statement = statement.where(AdminAuditEvent.action == action)
        if object_type is not None:
            statement = statement.where(AdminAuditEvent.object_type == object_type)
        if object_id is not None:
            statement = statement.where(AdminAuditEvent.object_id == object_id)
        if actor_identifier is not None:
            statement = statement.where(
                AdminAuditEvent.actor_identifier == actor_identifier
            )
        if reason is not None:
            statement = statement.where(AdminAuditEvent.reason.ilike(f"%{reason}%"))
        if occurred_after is not None:
            statement = statement.where(AdminAuditEvent.occurred_at >= occurred_after)
        if occurred_before is not None:
            statement = statement.where(AdminAuditEvent.occurred_at <= occurred_before)
        if cursor_position is not None:
            occurred_at, event_id = cursor_position
            statement = statement.where(
                or_(
                    AdminAuditEvent.occurred_at < occurred_at,
                    and_(
                        AdminAuditEvent.occurred_at == occurred_at,
                        AdminAuditEvent.id < event_id,
                    ),
                )
            )
        return list(
            self._session.scalars(
                statement.order_by(
                    AdminAuditEvent.occurred_at.desc(), AdminAuditEvent.id.desc()
                ).limit(limit)
            )
        )

    @staticmethod
    def _terminal_run_statement(**filters: object):
        """Keep UTC terminal inclusion identical for aggregate and keyset reads."""

        statement = select(AgentRun).where(
            AgentRun.finished_at.is_not(None),
            AgentRun.status.in_(("completed", "failed", "limit_reached")),
        )
        if (value := filters.get("occurred_after")) is not None:
            statement = statement.where(AgentRun.finished_at >= value)
        if (value := filters.get("occurred_before")) is not None:
            statement = statement.where(AgentRun.finished_at <= value)
        for name, column in (
            ("status", AgentRun.status),
            ("graph_version", AgentRun.graph_version),
            ("failure_code", AgentRun.failure_code),
        ):
            if (value := filters.get(name)) is not None:
                statement = statement.where(column == value)
        if (model := filters.get("model")) is not None:
            provider, version = str(model).split(":", 1)
            statement = statement.where(
                AgentRun.model_provider == provider, AgentRun.model_version == version
            )
        if (node := filters.get("failure_node")) is not None:
            statement = statement.where(
                select(AgentInvocation.id)
                .where(
                    AgentInvocation.run_id == AgentRun.id,
                    AgentInvocation.node_name == node,
                    AgentInvocation.failure_code.is_not(None),
                )
                .exists()
            )
        return statement

    def run_metrics(self, **filters: object) -> AdminRunMetricsResponse:
        terminal = self._terminal_run_statement(**filters).subquery()
        count, failures, p50, p95, cost = self._session.execute(
            select(
                func.count(terminal.c.id),
                func.coalesce(
                    func.sum(case((terminal.c.status == "failed", 1), else_=0)), 0
                ),
                func.percentile_cont(0.5).within_group(terminal.c.elapsed_ms),
                func.percentile_cont(0.95).within_group(terminal.c.elapsed_ms),
                func.coalesce(func.sum(terminal.c.estimated_cost_usd), 0),
            )
        ).one()
        terminal_count = int(count)
        return AdminRunMetricsResponse(
            terminal_count=terminal_count,
            failure_ratio=Decimal(int(failures)) / Decimal(terminal_count)
            if terminal_count
            else Decimal("0"),
            p50_elapsed_ms=round(p50) if p50 is not None else None,
            p95_elapsed_ms=round(p95) if p95 is not None else None,
            total_cost_usd=Decimal(str(cost)),
            from_=filters["occurred_after"],
            to=filters["occurred_before"],
        )

    def list_runs(
        self,
        *,
        limit: int,
        cursor_position: tuple[datetime, uuid.UUID] | None,
        **filters: object,
    ) -> list[AgentRun]:
        statement = self._terminal_run_statement(**filters)
        if cursor_position is not None:
            finished_at, run_id = cursor_position
            statement = statement.where(
                or_(
                    AgentRun.finished_at < finished_at,
                    and_(AgentRun.finished_at == finished_at, AgentRun.id < run_id),
                )
            )
        return list(
            self._session.scalars(
                statement.order_by(
                    AgentRun.finished_at.desc(), AgentRun.id.desc()
                ).limit(limit)
            )
        )

    def get_run(self, run_id: uuid.UUID) -> AgentRun | None:
        return self._session.scalar(
            self._terminal_run_statement().where(AgentRun.id == run_id)
        )

    def list_run_invocations(self, run_id: uuid.UUID) -> list[AgentInvocation]:
        """Expose only invocation ORM rows to the service whitelist mapper."""

        return list(
            self._session.scalars(
                select(AgentInvocation)
                .where(AgentInvocation.run_id == run_id)
                .order_by(AgentInvocation.created_at, AgentInvocation.id)
            )
        )

    def acquire_recipe_candidate_lock(self, command_key: str) -> None:
        self._session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
            {"key": f"recipe-candidate:{command_key}"},
        )

    def resolve_qualified_food_by_name(
        self, canonical_name: str
    ) -> list[QualifiedRecipeFoodReference]:
        imported = self._session.execute(
            select(FoodCatalogItem.id, FoodCatalogItem.canonical_name, NutritionCatalogVersion.version)
            .join(NutritionCatalogVersion, NutritionCatalogVersion.id == FoodCatalogItem.catalog_version_id)
            .where(
                    FoodCatalogItem.canonical_name == canonical_name,
                    FoodCatalogItem.is_qualified.is_(True),
                    FoodCatalogItem.energy_kcal_per_100g.is_not(None),
                    FoodCatalogItem.protein_g_per_100g.is_not(None),
                    FoodCatalogItem.fat_g_per_100g.is_not(None),
                    FoodCatalogItem.carbohydrate_g_per_100g.is_not(None),
            )
        ).all()
        latest = aliased(CatalogPublicationEligibility)
        latest_eligibility = (
            select(latest.id)
            .where(latest.publication_id == CatalogPublication.id)
            .order_by(latest.occurred_at.desc(), latest.id.desc())
            .limit(1)
            .scalar_subquery()
        )
        published = self._session.scalars(
            select(CatalogPublication)
            .join(
                CatalogActivePublication,
                CatalogActivePublication.publication_id == CatalogPublication.id,
            )
            .join(CatalogPublicationEligibility, CatalogPublicationEligibility.id == latest_eligibility)
            .where(
                CatalogPublicationEligibility.status == "eligible",
                CatalogPublication.snapshot["canonical_name"].as_string() == canonical_name,
            )
        ).all()
        published_by_fingerprint: dict[
            tuple[str, str, str, str], QualifiedRecipeFoodReference
        ] = {}
        for publication in published:
            snapshot = publication.snapshot
            # A CSV candidate can only name a dish, not a publication UUID.  Re-importing
            # the exact same released record therefore must not turn a safe lookup into
            # a false ambiguity.  A candidate's calculation uses these four values;
            # any difference between them remains an ambiguity and is rejected by the
            # service.  The chosen publication ID preserves the exact source record.
            fingerprint = tuple(
                str(snapshot.get(field, ""))
                for field in (
                    "energy_kcal_per_100g",
                    "protein_g_per_100g",
                    "fat_g_per_100g",
                    "carbohydrate_g_per_100g",
                )
            )
            reference = QualifiedRecipeFoodReference(
                id=publication.id,
                source_kind="catalog_publication",
                canonical_name=str(snapshot["canonical_name"]),
                nutrition_catalog_version="admin-publication-v1",
            )
            existing = published_by_fingerprint.get(fingerprint)
            if existing is None or str(reference.id) < str(existing.id):
                published_by_fingerprint[fingerprint] = reference

        return [
            *(
                QualifiedRecipeFoodReference(
                    id=item_id,
                    source_kind="food_catalog_item",
                    canonical_name=name,
                    nutrition_catalog_version=version,
                )
                for item_id, name, version in imported
            ),
            *sorted(published_by_fingerprint.values(), key=lambda item: str(item.id)),
        ]

    def add_recipe_candidate(
        self, candidate: ManagedRecipeCandidate
    ) -> ManagedRecipeCandidate:
        self._session.add(candidate)
        self._session.flush()
        return candidate

    def get_recipe_candidate(
        self, candidate_id: uuid.UUID, *, for_update: bool = False
    ) -> ManagedRecipeCandidate | None:
        statement = select(ManagedRecipeCandidate).where(
            ManagedRecipeCandidate.id == candidate_id
        )
        return self._session.scalar(
            statement.with_for_update() if for_update else statement
        )

    def list_recipe_candidates(
        self,
        *,
        search: str,
        meal_slot: str | None,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[ManagedRecipeCandidate], int]:
        statement = select(ManagedRecipeCandidate).where(
            ManagedRecipeCandidate.deleted_at.is_(None)
        )
        if search:
            statement = statement.where(
                ManagedRecipeCandidate.catalog_food_name.icontains(search, autoescape=True)
            )
        if meal_slot:
            statement = statement.where(ManagedRecipeCandidate.meal_slot == meal_slot)
        if status:
            statement = statement.where(ManagedRecipeCandidate.status == status)
        total = int(
            self._session.scalar(select(func.count()).select_from(statement.subquery()))
            or 0
        )
        return list(
            self._session.scalars(
                statement.order_by(
                    ManagedRecipeCandidate.created_at.desc(),
                    ManagedRecipeCandidate.id.desc(),
                )
                .offset(offset)
                .limit(limit)
            )
        ), total
