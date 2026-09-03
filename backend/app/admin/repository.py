"""SQLAlchemy adapter for admin role reads, locks, and audit insertion."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import and_, case, exists, func, or_, select, text
from sqlalchemy.orm import Session

from app.admin.models import AdminAuditEvent, AdminRoleAudit, CatalogActivePublication, CatalogDraft, CatalogDraftChangeSet, CatalogDraftReview, CatalogDraftRevision, CatalogPublication, CatalogPublicationEligibility
from app.agent.models import AgentInvocation, AgentRun, AgentRuntimeConfigVersion
from app.admin.schemas import AdminRunMetricsResponse
from app.auth.models import User, UserRole


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

    def add_audit(self, audit: AdminRoleAudit) -> AdminRoleAudit:
        self._session.add(audit)
        self._session.flush()
        return audit

    def add_audit_event(self, event: AdminAuditEvent) -> AdminAuditEvent:
        self._session.add(event)
        self._session.flush()
        return event

    def acquire_runtime_config_lock(self) -> None:
        """Serialize active-policy selection and version allocation per transaction."""

        self._session.execute(text("SELECT pg_advisory_xact_lock(60516019)"))

    def get_runtime_config_command(self, command_key: str) -> AgentRuntimeConfigVersion | None:
        return self._session.scalar(
            select(AgentRuntimeConfigVersion).where(AgentRuntimeConfigVersion.command_key == command_key)
        )

    def get_active_runtime_config(self) -> AgentRuntimeConfigVersion | None:
        return self._session.scalar(
            select(AgentRuntimeConfigVersion).order_by(AgentRuntimeConfigVersion.version.desc()).limit(1)
        )

    def next_runtime_config_version(self) -> int:
        return int(self._session.scalar(select(func.coalesce(func.max(AgentRuntimeConfigVersion.version), 0))) or 0) + 1

    def add_runtime_config_version(self, version: AgentRuntimeConfigVersion) -> AgentRuntimeConfigVersion:
        self._session.add(version)
        self._session.flush()
        return version

    def get_catalog_draft(self, draft_id: uuid.UUID, *, for_update: bool = False) -> CatalogDraft | None:
        statement = select(CatalogDraft).where(CatalogDraft.id == draft_id)
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def get_catalog_draft_command(self, command_key: str) -> CatalogDraftChangeSet | None:
        return self._session.scalar(select(CatalogDraftChangeSet).where(CatalogDraftChangeSet.command_key == command_key))

    def add_catalog_draft(self, draft: CatalogDraft) -> CatalogDraft:
        self._session.add(draft)
        self._session.flush()
        return draft

    def add_catalog_draft_change_set(self, change_set: CatalogDraftChangeSet) -> CatalogDraftChangeSet:
        self._session.add(change_set)
        self._session.flush()
        return change_set

    def add_catalog_draft_revision(self, revision: CatalogDraftRevision) -> CatalogDraftRevision:
        self._session.add(revision)
        self._session.flush()
        return revision

    def acquire_catalog_publication_lock(self, draft_id: uuid.UUID) -> None:
        # Transaction-scoped advisory locking serializes publication even before a
        # pointer row exists, closing the first-publish race without global locks.
        self._session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:draft_id))"), {"draft_id": str(draft_id)})

    def get_catalog_review(self, *, draft_id: uuid.UUID, revision: int) -> CatalogDraftReview | None:
        return self._session.scalar(select(CatalogDraftReview).where(CatalogDraftReview.draft_id == draft_id, CatalogDraftReview.draft_revision == revision))

    def add_catalog_review(self, review: CatalogDraftReview) -> CatalogDraftReview:
        self._session.add(review)
        self._session.flush()
        return review

    def get_catalog_publication_command(self, command_key: str) -> CatalogPublication | None:
        return self._session.scalar(select(CatalogPublication).where(CatalogPublication.command_key == command_key))

    def add_catalog_publication(self, publication: CatalogPublication) -> CatalogPublication:
        self._session.add(publication)
        self._session.flush()
        return publication

    def get_active_catalog_publication(self, draft_id: uuid.UUID) -> CatalogPublication | None:
        return self._session.scalar(select(CatalogPublication).join(CatalogActivePublication, CatalogActivePublication.publication_id == CatalogPublication.id).where(CatalogActivePublication.draft_id == draft_id))

    def advance_active_catalog_publication(self, *, draft_id: uuid.UUID, publication_id: uuid.UUID) -> CatalogActivePublication:
        pointer = self._session.get(CatalogActivePublication, draft_id)
        if pointer is None:
            pointer = CatalogActivePublication(draft_id=draft_id, publication_id=publication_id, advanced_at=datetime.now().astimezone())
            self._session.add(pointer)
        else:
            pointer.publication_id = publication_id
            pointer.advanced_at = datetime.now().astimezone()
        self._session.flush()
        return pointer

    def get_catalog_publication(self, publication_id: uuid.UUID) -> CatalogPublication | None:
        return self._session.get(CatalogPublication, publication_id)

    def get_catalog_eligibility_command(self, command_key: str) -> CatalogPublicationEligibility | None:
        return self._session.scalar(select(CatalogPublicationEligibility).where(CatalogPublicationEligibility.command_key == command_key))

    def get_latest_catalog_eligibility(self, publication_id: uuid.UUID) -> CatalogPublicationEligibility | None:
        return self._session.scalar(
            select(CatalogPublicationEligibility)
            .where(CatalogPublicationEligibility.publication_id == publication_id)
            .order_by(CatalogPublicationEligibility.occurred_at.desc(), CatalogPublicationEligibility.id.desc())
            .limit(1)
        )

    def add_catalog_eligibility(self, eligibility: CatalogPublicationEligibility) -> CatalogPublicationEligibility:
        self._session.add(eligibility)
        self._session.flush()
        return eligibility

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
            statement = statement.where(AdminAuditEvent.actor_identifier == actor_identifier)
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
                    and_(AdminAuditEvent.occurred_at == occurred_at, AdminAuditEvent.id < event_id),
                )
            )
        return list(
            self._session.scalars(
                statement.order_by(AdminAuditEvent.occurred_at.desc(), AdminAuditEvent.id.desc()).limit(limit)
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
        for name, column in (("status", AgentRun.status), ("graph_version", AgentRun.graph_version), ("failure_code", AgentRun.failure_code)):
            if (value := filters.get(name)) is not None:
                statement = statement.where(column == value)
        if (model := filters.get("model")) is not None:
            provider, version = str(model).split(":", 1)
            statement = statement.where(AgentRun.model_provider == provider, AgentRun.model_version == version)
        if (node := filters.get("failure_node")) is not None:
            statement = statement.where(
                select(AgentInvocation.id).where(
                    AgentInvocation.run_id == AgentRun.id,
                    AgentInvocation.node_name == node,
                    AgentInvocation.failure_code.is_not(None),
                ).exists()
            )
        return statement

    def run_metrics(self, **filters: object) -> AdminRunMetricsResponse:
        terminal = self._terminal_run_statement(**filters).subquery()
        count, failures, p50, p95, cost = self._session.execute(
            select(
                func.count(terminal.c.id),
                func.coalesce(func.sum(case((terminal.c.status == "failed", 1), else_=0)), 0),
                func.percentile_cont(0.5).within_group(terminal.c.elapsed_ms),
                func.percentile_cont(0.95).within_group(terminal.c.elapsed_ms),
                func.coalesce(func.sum(terminal.c.estimated_cost_usd), 0),
            )
        ).one()
        terminal_count = int(count)
        return AdminRunMetricsResponse(
            terminal_count=terminal_count,
            failure_ratio=Decimal(int(failures)) / Decimal(terminal_count) if terminal_count else Decimal("0"),
            p50_elapsed_ms=round(p50) if p50 is not None else None,
            p95_elapsed_ms=round(p95) if p95 is not None else None,
            total_cost_usd=Decimal(str(cost)),
        )

    def list_runs(self, *, limit: int, cursor_position: tuple[datetime, uuid.UUID] | None, **filters: object) -> list[AgentRun]:
        statement = self._terminal_run_statement(**filters)
        if cursor_position is not None:
            finished_at, run_id = cursor_position
            statement = statement.where(or_(AgentRun.finished_at < finished_at, and_(AgentRun.finished_at == finished_at, AgentRun.id < run_id)))
        return list(self._session.scalars(statement.order_by(AgentRun.finished_at.desc(), AgentRun.id.desc()).limit(limit)))

    def get_run(self, run_id: uuid.UUID) -> AgentRun | None:
        return self._session.scalar(self._terminal_run_statement().where(AgentRun.id == run_id))

    def list_run_invocations(self, run_id: uuid.UUID) -> list[AgentInvocation]:
        """Expose only invocation ORM rows to the service whitelist mapper."""

        return list(self._session.scalars(
            select(AgentInvocation)
            .where(AgentInvocation.run_id == run_id)
            .order_by(AgentInvocation.created_at, AgentInvocation.id)
        ))
