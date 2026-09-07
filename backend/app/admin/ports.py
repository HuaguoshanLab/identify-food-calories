"""Persistence capabilities consumed by admin authorization services."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

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
from app.auth.models import User
from app.admin.schemas import CatalogListQuery
from app.nutrition.models import FoodCatalogItem
from app.planning.models import ManagedRecipeCandidate


class AdminRepository(Protocol):
    def acquire_bootstrap_lock(self) -> None: ...

    def get_user_by_id(self, user_id: uuid.UUID) -> User | None: ...

    def get_user_by_email(self, normalized_email: str) -> User | None: ...

    def get_user_for_update(self, user_id: uuid.UUID) -> User | None: ...

    def has_active_admin(self) -> bool: ...

    def add_audit(self, audit: AdminRoleAudit) -> AdminRoleAudit: ...

    def add_audit_event(self, event: AdminAuditEvent) -> AdminAuditEvent: ...

    def get_audit_event_by_command_key(
        self, command_key: str
    ) -> AdminAuditEvent | None: ...

    def acquire_runtime_config_lock(self) -> None: ...

    def get_runtime_config_command(
        self, command_key: str
    ) -> AgentRuntimeConfigVersion | None: ...

    def get_active_runtime_config(self) -> AgentRuntimeConfigVersion | None: ...

    def next_runtime_config_version(self) -> int: ...

    def add_runtime_config_version(
        self, version: AgentRuntimeConfigVersion
    ) -> AgentRuntimeConfigVersion: ...

    def get_catalog_draft(
        self, draft_id: uuid.UUID, *, for_update: bool = False
    ) -> CatalogDraft | None: ...

    def list_catalog_drafts(
        self, *, query: CatalogListQuery, limit: int, offset: int
    ) -> tuple[list[CatalogDraft], int]: ...

    def acquire_catalog_import_lock(self, command_key: str) -> None: ...

    def get_catalog_draft_command(
        self, command_key: str
    ) -> CatalogDraftChangeSet | None: ...

    def add_catalog_draft(self, draft: CatalogDraft) -> CatalogDraft: ...

    def add_catalog_draft_change_set(
        self, change_set: CatalogDraftChangeSet
    ) -> CatalogDraftChangeSet: ...

    def add_catalog_draft_revision(
        self, revision: CatalogDraftRevision
    ) -> CatalogDraftRevision: ...

    def acquire_catalog_publication_lock(self, draft_id: uuid.UUID) -> None: ...

    def get_catalog_review(
        self, *, draft_id: uuid.UUID, revision: int
    ) -> CatalogDraftReview | None: ...

    def add_catalog_review(self, review: CatalogDraftReview) -> CatalogDraftReview: ...

    def get_catalog_publication_command(
        self, command_key: str
    ) -> CatalogPublication | None: ...

    def add_catalog_publication(
        self, publication: CatalogPublication
    ) -> CatalogPublication: ...

    def get_active_catalog_publication(
        self, draft_id: uuid.UUID
    ) -> CatalogPublication | None: ...

    def advance_active_catalog_publication(
        self, *, draft_id: uuid.UUID, publication_id: uuid.UUID
    ) -> CatalogActivePublication: ...

    def get_catalog_publication(
        self, publication_id: uuid.UUID
    ) -> CatalogPublication | None: ...

    def get_catalog_eligibility_command(
        self, command_key: str
    ) -> CatalogPublicationEligibility | None: ...

    def get_latest_catalog_eligibility(
        self, publication_id: uuid.UUID
    ) -> CatalogPublicationEligibility | None: ...

    def add_catalog_eligibility(
        self, eligibility: CatalogPublicationEligibility
    ) -> CatalogPublicationEligibility: ...

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
    ) -> list[AdminAuditEvent]: ...

    def run_metrics(self, **filters: object) -> object: ...

    def list_runs(
        self,
        *,
        limit: int,
        cursor_position: tuple[datetime, uuid.UUID] | None,
        **filters: object,
    ) -> list[AgentRun]: ...

    def get_run(self, run_id: uuid.UUID) -> AgentRun | None: ...

    def list_run_invocations(self, run_id: uuid.UUID) -> list[AgentInvocation]: ...

    def acquire_recipe_candidate_lock(self, command_key: str) -> None: ...

    def resolve_qualified_food_by_name(
        self, canonical_name: str
    ) -> list[FoodCatalogItem]: ...

    def add_recipe_candidate(
        self, candidate: ManagedRecipeCandidate
    ) -> ManagedRecipeCandidate: ...

    def get_recipe_candidate(
        self, candidate_id: uuid.UUID, *, for_update: bool = False
    ) -> ManagedRecipeCandidate | None: ...

    def list_recipe_candidates(
        self,
        *,
        search: str,
        meal_slot: str | None,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[ManagedRecipeCandidate], int]: ...
