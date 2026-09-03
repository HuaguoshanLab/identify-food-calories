"""RED contracts for review, immutable publication and eligibility withdrawal."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.admin.models import AdminAuditEvent, CatalogDraft, CatalogPublication
from app.admin.schemas import CatalogDraftCreateCommand, CatalogLifecycleCommand
from app.admin.service import AdminService, CatalogDraftConflict
from app.auth.models import User, UserRole


NOW = datetime(2026, 9, 3, tzinfo=UTC)


def _admin() -> User:
    return User(
        id=uuid.uuid4(), email="lifecycle-admin@example.test", password_hash="hash",
        role=UserRole.ADMIN.value, is_active=True, email_verified_at=NOW,
        created_at=NOW, updated_at=NOW,
    )


def _command() -> CatalogDraftCreateCommand:
    return CatalogDraftCreateCommand(
        canonical_name="Oats", aliases=["rolled oats"], energy_kcal_per_100g=Decimal("389"),
        protein_g_per_100g=Decimal("16.9"), fat_g_per_100g=Decimal("6.9"),
        carbohydrate_g_per_100g=Decimal("66.3"), source_name="USDA",
        source_url="https://fdc.nal.usda.gov/", authorization_status="authorized",
        reason="verified source",
    )


class FakeLifecycleRepository:
    """Minimal in-memory port proving service protocol before PostgreSQL coverage."""

    def __init__(self, actor: User) -> None:
        self.actor = actor
        self.drafts: dict[uuid.UUID, CatalogDraft] = {}
        self.publications: dict[uuid.UUID, CatalogPublication] = {}
        self.commands: dict[str, object] = {}
        self.events: list[AdminAuditEvent] = []

    def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.actor if user_id == self.actor.id else None

    def get_catalog_draft(self, draft_id: uuid.UUID, *, for_update: bool = False) -> CatalogDraft | None:
        del for_update
        return self.drafts.get(draft_id)

    def get_catalog_draft_command(self, command_key: str):
        return self.commands.get(command_key)

    def add_catalog_draft(self, draft: CatalogDraft) -> CatalogDraft:
        self.drafts[draft.id] = draft
        return draft

    def add_catalog_draft_change_set(self, change_set):
        self.commands[change_set.command_key] = change_set
        return change_set

    def add_catalog_draft_revision(self, revision):
        return revision

    def acquire_catalog_publication_lock(self, draft_id: uuid.UUID) -> None:
        del draft_id

    def get_catalog_review(self, *, draft_id: uuid.UUID, revision: int):
        return self.commands.get(f"review:{draft_id}:{revision}")

    def add_catalog_review(self, review):
        self.commands[f"review:{review.draft_id}:{review.draft_revision}"] = review
        self.commands[review.command_key] = review
        return review

    def get_catalog_publication_command(self, command_key: str):
        return self.commands.get(command_key)

    def add_catalog_publication(self, publication: CatalogPublication) -> CatalogPublication:
        self.publications[publication.id] = publication
        self.commands[publication.command_key] = publication
        return publication

    def get_active_catalog_publication(self, draft_id: uuid.UUID):
        return next((item for item in self.publications.values() if item.draft_id == draft_id), None)

    def advance_active_catalog_publication(self, *, draft_id: uuid.UUID, publication_id: uuid.UUID) -> None:
        del draft_id, publication_id

    def get_catalog_publication(self, publication_id: uuid.UUID):
        return self.publications.get(publication_id)

    def get_catalog_eligibility_command(self, command_key: str):
        return self.commands.get(command_key)

    def add_catalog_eligibility(self, eligibility):
        self.commands[eligibility.command_key] = eligibility
        return eligibility

    def add_audit_event(self, event: AdminAuditEvent) -> AdminAuditEvent:
        self.events.append(event)
        return event


def test_review_publish_is_idempotent_immutable_and_audited() -> None:
    actor = _admin()
    repository = FakeLifecycleRepository(actor)
    service = AdminService(repository=repository, now=lambda: NOW)
    draft = service.create_catalog_draft(actor_user_id=actor.id, command=_command(), command_key="create-lifecycle-0001")
    lifecycle = CatalogLifecycleCommand(reason="checked evidence", confirm=True)

    review = service.review_catalog_draft(
        actor_user_id=actor.id, draft_id=draft.id, expected_revision=1,
        command=lifecycle, command_key="review-lifecycle-0001",
    )
    published = service.publish_catalog_draft(
        actor_user_id=actor.id, draft_id=draft.id, expected_revision=1,
        command=lifecycle, command_key="publish-lifecycle-0001",
    )
    replay = service.publish_catalog_draft(
        actor_user_id=actor.id, draft_id=draft.id, expected_revision=1,
        command=lifecycle, command_key="publish-lifecycle-0001",
    )

    assert review.content_hash == published.content_hash
    assert replay.id == published.id
    assert published.snapshot["canonical_name"] == "Oats"
    assert [event.action for event in repository.events[-2:]] == ["catalog.review", "catalog.publish"]


def test_publish_requires_current_review_and_confirmed_server_command() -> None:
    actor = _admin()
    repository = FakeLifecycleRepository(actor)
    service = AdminService(repository=repository, now=lambda: NOW)
    draft = service.create_catalog_draft(actor_user_id=actor.id, command=_command(), command_key="create-lifecycle-0002")

    with pytest.raises(CatalogDraftConflict):
        service.publish_catalog_draft(
            actor_user_id=actor.id, draft_id=draft.id, expected_revision=1,
            command=CatalogLifecycleCommand(reason="publish", confirm=True), command_key="publish-lifecycle-0002",
        )
    with pytest.raises(ValueError):
        CatalogLifecycleCommand(reason="publish", confirm=False)
