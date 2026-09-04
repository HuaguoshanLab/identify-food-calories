"""RED contracts for server-authoritative nutrition catalog drafts."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.admin.models import AdminAuditEvent, CatalogDraft, CatalogDraftChangeSet, CatalogDraftRevision
from app.admin.schemas import CatalogDraftCreateCommand, CatalogDraftPatchCommand, CatalogDraftPreviewCommand
from app.admin.service import AdminPermissionDenied, AdminService, CatalogDraftConflict
from app.auth.models import User, UserRole


NOW = datetime(2026, 9, 2, tzinfo=UTC)


def _admin(role: str = UserRole.ADMIN.value) -> User:
    return User(
        id=uuid.uuid4(), email="catalog-admin@example.com", password_hash="hash", role=role,
        is_active=True, email_verified_at=NOW, created_at=NOW, updated_at=NOW,
    )


class FakeCatalogDraftRepository:
    def __init__(self, user: User) -> None:
        self.user = user
        self.users: dict[uuid.UUID, User] = {}
        self.drafts: dict[uuid.UUID, CatalogDraft] = {}
        self.events: list[AdminAuditEvent] = []
        self.commands: dict[str, CatalogDraftChangeSet] = {}
        self.revisions: list[CatalogDraftRevision] = []

    def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.user if self.user.id == user_id else self.users.get(user_id)

    def get_catalog_draft(self, draft_id: uuid.UUID) -> CatalogDraft | None:
        return self.drafts.get(draft_id)

    def get_catalog_draft_command(self, command_key: str) -> CatalogDraftChangeSet | None:
        return self.commands.get(command_key)

    def add_catalog_draft(self, draft: CatalogDraft) -> CatalogDraft:
        self.drafts[draft.id] = draft
        return draft

    def add_catalog_draft_change_set(self, change_set: CatalogDraftChangeSet) -> CatalogDraftChangeSet:
        self.commands[change_set.command_key] = change_set
        return change_set

    def add_catalog_draft_revision(self, revision: CatalogDraftRevision) -> CatalogDraftRevision:
        self.revisions.append(revision)
        return revision

    def add_audit_event(self, event: AdminAuditEvent) -> AdminAuditEvent:
        self.events.append(event)
        return event


def _create() -> CatalogDraftCreateCommand:
    return CatalogDraftCreateCommand(
        canonical_name="Oats", aliases=["rolled oats"], energy_kcal_per_100g=Decimal("389"),
        protein_g_per_100g=Decimal("16.9"), fat_g_per_100g=Decimal("6.9"),
        carbohydrate_g_per_100g=Decimal("66.3"), source_name="USDA", source_url="https://fdc.nal.usda.gov/",
        authorization_status="authorized", reason="verified source import",
    )


def test_catalog_draft_dto_is_strict_and_rejects_unsafe_input() -> None:
    payload = _create().model_dump(exclude={"reason"})
    with pytest.raises(ValidationError):
        CatalogDraftCreateCommand(**payload, reason=" ")
    with pytest.raises(ValidationError):
        CatalogDraftCreateCommand(**(payload | {"source_url": "http://unsafe.example", "reason": "valid"}))
    with pytest.raises(ValidationError):
        CatalogDraftCreateCommand(**(payload | {"aliases": [" "], "reason": "valid"}))
    with pytest.raises(ValidationError):
        CatalogDraftCreateCommand(**(payload | {"energy_kcal_per_100g": Decimal("-1"), "reason": "valid"}))
    with pytest.raises(ValidationError):
        CatalogDraftCreateCommand(**payload, reason="valid", unexpected="nope")


def test_create_and_patch_compute_audit_diff_and_replay_same_command() -> None:
    actor = _admin()
    repository = FakeCatalogDraftRepository(actor)
    service = AdminService(repository=repository, now=lambda: NOW)
    created = service.create_catalog_draft(actor_user_id=actor.id, command=_create(), command_key="create-00000001")
    replay = service.create_catalog_draft(actor_user_id=actor.id, command=_create(), command_key="create-00000001")

    assert replay.id == created.id
    assert len(repository.events) == 1
    patched = service.patch_catalog_draft(
        actor_user_id=actor.id, draft_id=created.id, expected_revision=1, command_key="patch-00000001",
        command=CatalogDraftPatchCommand(canonical_name="Organic oats", reason="clarified label"),
    )
    assert patched.revision == 2
    event = repository.events[-1]
    assert event.before_diff == {"canonical_name": "Oats"}
    assert event.after_diff == {"canonical_name": "Organic oats"}


def test_preview_and_read_use_current_database_draft_and_server_computed_impact() -> None:
    actor = _admin()
    repository = FakeCatalogDraftRepository(actor)
    service = AdminService(repository=repository, now=lambda: NOW)
    created = service.create_catalog_draft(actor_user_id=actor.id, command=_create(), command_key="create-000000-preview")

    preview_payload = _create().model_dump(exclude={"reason"}) | {
        "draft_id": created.id,
        "canonical_name": "Organic oats",
        "energy_kcal_per_100g": Decimal("401"),
        "authorization_status": "pending",
    }
    preview = service.preview_catalog_draft(
        actor_user_id=actor.id,
        command=CatalogDraftPreviewCommand(**preview_payload),
    )

    assert preview.draft_id == created.id
    assert preview.base_revision == created.revision
    assert [(item.field, item.before, item.after) for item in preview.field_diffs] == [
        ("canonical_name", "Oats", "Organic oats"),
        ("energy_kcal_per_100g", "389", "401"),
        ("authorization_status", "authorized", "pending"),
    ]
    assert preview.impact_categories == ["catalog_identity", "nutrition_per_100g", "authorization_status"]
    assert service.read_catalog_draft(actor_user_id=actor.id, draft_id=created.id) == created
    assert repository.events[-1].action == "catalog_draft.create"


def test_patch_rejects_stale_revision_and_non_admin() -> None:
    actor = _admin()
    repository = FakeCatalogDraftRepository(actor)
    service = AdminService(repository=repository, now=lambda: NOW)
    created = service.create_catalog_draft(actor_user_id=actor.id, command=_create(), command_key="create-00000002")
    with pytest.raises(CatalogDraftConflict):
        service.patch_catalog_draft(
            actor_user_id=actor.id, draft_id=created.id, expected_revision=99, command_key="patch-00000002",
            command=CatalogDraftPatchCommand(canonical_name="Other oats", reason="wrong concurrent edit"),
        )
    repository.user = _admin(UserRole.USER.value)
    with pytest.raises(AdminPermissionDenied):
        service.create_catalog_draft(actor_user_id=repository.user.id, command=_create(), command_key="create-00000003")


def test_create_and_patch_replays_require_current_active_database_admin() -> None:
    actor = _admin()
    normal_user = _admin(UserRole.USER.value)
    repository = FakeCatalogDraftRepository(actor)
    repository.users[normal_user.id] = normal_user
    service = AdminService(repository=repository, now=lambda: NOW)

    created = service.create_catalog_draft(
        actor_user_id=actor.id, command=_create(), command_key="create-replay-rbac-0001",
    )
    with pytest.raises(AdminPermissionDenied):
        service.create_catalog_draft(
            actor_user_id=normal_user.id, command=_create(), command_key="create-replay-rbac-0001",
        )

    patched = service.patch_catalog_draft(
        actor_user_id=actor.id, draft_id=created.id, expected_revision=1,
        command=CatalogDraftPatchCommand(canonical_name="Organic oats", reason="clarified label"),
        command_key="patch-replay-rbac-0001",
    )
    patch = CatalogDraftPatchCommand(canonical_name="Organic oats", reason="clarified label")
    with pytest.raises(AdminPermissionDenied):
        service.patch_catalog_draft(
            actor_user_id=normal_user.id, draft_id=created.id, expected_revision=1,
            command=patch, command_key="patch-replay-rbac-0001",
        )

    actor.role = UserRole.USER.value
    with pytest.raises(AdminPermissionDenied):
        service.create_catalog_draft(
            actor_user_id=actor.id, command=_create(), command_key="create-replay-rbac-0001",
        )
    with pytest.raises(AdminPermissionDenied):
        service.patch_catalog_draft(
            actor_user_id=actor.id, draft_id=created.id, expected_revision=1,
            command=patch, command_key="patch-replay-rbac-0001",
        )
    assert patched.revision == 2


def test_catalog_mutation_rolls_back_when_audit_transaction_fails() -> None:
    actor = _admin()
    repository = FakeCatalogDraftRepository(actor)
    rollbacks: list[bool] = []
    service = AdminService(
        repository=repository, now=lambda: NOW,
        commit=lambda: (_ for _ in ()).throw(RuntimeError("database failure")),
        rollback=lambda: rollbacks.append(True),
    )

    with pytest.raises(RuntimeError):
        service.create_catalog_draft(actor_user_id=actor.id, command=_create(), command_key="create-00000004")

    assert rollbacks == [True]
