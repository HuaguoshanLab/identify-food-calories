"""Persistence capabilities consumed by admin authorization services."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from app.admin.models import AdminAuditEvent, AdminRoleAudit, CatalogDraft, CatalogDraftChangeSet, CatalogDraftRevision
from app.auth.models import User


class AdminRepository(Protocol):
    def acquire_bootstrap_lock(self) -> None: ...

    def get_user_by_id(self, user_id: uuid.UUID) -> User | None: ...

    def get_user_by_email(self, normalized_email: str) -> User | None: ...

    def get_user_for_update(self, user_id: uuid.UUID) -> User | None: ...

    def has_active_admin(self) -> bool: ...

    def add_audit(self, audit: AdminRoleAudit) -> AdminRoleAudit: ...

    def add_audit_event(self, event: AdminAuditEvent) -> AdminAuditEvent: ...

    def get_catalog_draft(self, draft_id: uuid.UUID) -> CatalogDraft | None: ...

    def get_catalog_draft_command(self, command_key: str) -> CatalogDraftChangeSet | None: ...

    def add_catalog_draft(self, draft: CatalogDraft) -> CatalogDraft: ...

    def add_catalog_draft_change_set(self, change_set: CatalogDraftChangeSet) -> CatalogDraftChangeSet: ...

    def add_catalog_draft_revision(self, revision: CatalogDraftRevision) -> CatalogDraftRevision: ...

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
