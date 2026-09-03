"""PostgreSQL contracts for publication pointers and future-use eligibility overlays."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import uuid

from sqlalchemy import select

from app.admin.models import CatalogActivePublication, CatalogPublication, CatalogPublicationEligibility
from app.admin.repository import SqlAlchemyAdminRepository
from app.admin.schemas import CatalogDraftCreateCommand, CatalogLifecycleCommand
from app.admin.service import AdminService
from app.auth.models import User, UserRole


def _actor(now: datetime) -> User:
    return User(id=uuid.uuid4(), email=f"publication-{uuid.uuid4().hex}@example.test", password_hash="hash", role=UserRole.ADMIN.value, is_active=True, email_verified_at=now, created_at=now, updated_at=now)


def _draft_command() -> CatalogDraftCreateCommand:
    return CatalogDraftCreateCommand(canonical_name="Oats", aliases=["oats"], energy_kcal_per_100g=Decimal("389"), protein_g_per_100g=Decimal("16"), fat_g_per_100g=Decimal("7"), carbohydrate_g_per_100g=Decimal("66"), source_name="USDA", source_url="https://fdc.nal.usda.gov/", authorization_status="authorized", reason="source checked")


def test_published_pointer_has_one_immutable_publication_and_disqualification_is_append_only(db_session) -> None:
    now = datetime.now(UTC)
    actor = _actor(now)
    db_session.add(actor)
    db_session.flush()
    service = AdminService(repository=SqlAlchemyAdminRepository(db_session), now=lambda: now, commit=db_session.commit, rollback=db_session.rollback)
    draft = service.create_catalog_draft(actor_user_id=actor.id, command=_draft_command(), command_key="create-publish-pg-0001")
    command = CatalogLifecycleCommand(reason="review complete", confirm=True)
    service.review_catalog_draft(actor_user_id=actor.id, draft_id=draft.id, expected_revision=1, command=command, command_key="review-publish-pg-0001")
    publication = service.publish_catalog_draft(actor_user_id=actor.id, draft_id=draft.id, expected_revision=1, command=command, command_key="publish-pg-0001")
    service.disqualify_catalog_publication(actor_user_id=actor.id, publication_id=publication.id, command=CatalogLifecycleCommand(reason="authorization revoked", confirm=True), command_key="disqualify-pg-0001")

    assert db_session.scalar(select(CatalogActivePublication).where(CatalogActivePublication.draft_id == draft.id)).publication_id == publication.id
    assert db_session.scalar(select(CatalogPublication).where(CatalogPublication.id == publication.id)).snapshot["canonical_name"] == "Oats"
    history = list(db_session.scalars(select(CatalogPublicationEligibility).where(CatalogPublicationEligibility.publication_id == publication.id).order_by(CatalogPublicationEligibility.occurred_at)))
    assert [item.status for item in history] == ["eligible", "disqualified"]
