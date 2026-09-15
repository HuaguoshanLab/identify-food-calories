"""PostgreSQL contracts for publication pointers and future-use eligibility overlays."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import threading
import uuid
import asyncio

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin.models import CatalogActivePublication, CatalogPublication, CatalogPublicationEligibility
from app.admin.repository import SqlAlchemyAdminRepository
from app.admin.schemas import CatalogDraftCreateCommand, CatalogLifecycleCommand
from app.admin.service import AdminService
from app.auth.models import User, UserRole
from app.nutrition.repository import ADMIN_PUBLICATION_VERSION, SqlAlchemyNutritionRepository
from app.nutrition.schemas import FoodSearchInput, NutritionAction
from app.nutrition.service import NutritionService


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
    lifecycle_preview = service.preview_catalog_lifecycle(actor_user_id=actor.id, draft_id=draft.id)
    assert lifecycle_preview.publication is not None
    assert lifecycle_preview.publication.id == publication.id
    assert lifecycle_preview.publication.eligibility == "eligible"
    assert {item.change for item in lifecycle_preview.field_diffs} == {"unchanged"}
    assert "snapshot" not in lifecycle_preview.model_dump()
    nutrition = SqlAlchemyNutritionRepository(db_session)
    assert nutrition.get_qualified_food(food_id=publication.id, catalog_version=ADMIN_PUBLICATION_VERSION) is not None
    service.disqualify_catalog_publication(actor_user_id=actor.id, publication_id=publication.id, command=CatalogLifecycleCommand(reason="authorization revoked", confirm=True), command_key="disqualify-pg-0001")
    disqualified_preview = service.preview_catalog_lifecycle(actor_user_id=actor.id, draft_id=draft.id)
    assert disqualified_preview.publication is not None
    assert disqualified_preview.publication.eligibility == "disqualified"

    assert db_session.scalar(select(CatalogActivePublication).where(CatalogActivePublication.draft_id == draft.id)).publication_id == publication.id
    assert db_session.scalar(select(CatalogPublication).where(CatalogPublication.id == publication.id)).snapshot["canonical_name"] == "Oats"
    history = list(db_session.scalars(select(CatalogPublicationEligibility).where(CatalogPublicationEligibility.publication_id == publication.id).order_by(CatalogPublicationEligibility.occurred_at)))
    assert [item.status for item in history] == ["eligible", "disqualified"]
    assert nutrition.get_qualified_food(food_id=publication.id, catalog_version=ADMIN_PUBLICATION_VERSION) is None


def test_published_food_is_searchable_by_its_canonical_name_when_aliases_differ(db_session) -> None:
    now = datetime.now(UTC)
    actor = _actor(now)
    db_session.add(actor)
    db_session.flush()
    service = AdminService(repository=SqlAlchemyAdminRepository(db_session), now=lambda: now, commit=db_session.commit, rollback=db_session.rollback)
    draft = service.create_catalog_draft(
        actor_user_id=actor.id,
        command=CatalogDraftCreateCommand(
            canonical_name="白米饭", aliases=["baimifan", "白饭"],
            energy_kcal_per_100g=Decimal("116"), protein_g_per_100g=Decimal("2.6"),
            fat_g_per_100g=Decimal("0.3"), carbohydrate_g_per_100g=Decimal("25.9"),
            source_name="USDA", source_url="https://fdc.nal.usda.gov/", authorization_status="authorized",
            reason="canonical-name search coverage",
        ),
        command_key="create-canonical-search-pg-0001",
    )
    command = CatalogLifecycleCommand(reason="review complete", confirm=True)
    service.review_catalog_draft(actor_user_id=actor.id, draft_id=draft.id, expected_revision=1, command=command, command_key="review-canonical-search-pg-0001")
    publication = service.publish_catalog_draft(actor_user_id=actor.id, draft_id=draft.id, expected_revision=1, command=command, command_key="publish-canonical-search-pg-0001")

    result = asyncio.run(NutritionService(repository=SqlAlchemyNutritionRepository(db_session)).search_food_catalog(FoodSearchInput(query="白米饭")))

    assert result.action is NutritionAction.PASS
    assert result.selected_food is not None
    assert result.selected_food.id == publication.id
    assert result.selected_food.catalog_version == ADMIN_PUBLICATION_VERSION


def test_two_postgresql_publishers_share_one_active_immutable_pointer(test_engine) -> None:
    now = datetime.now(UTC)
    with Session(test_engine) as session:
        actor = _actor(now)
        session.add(actor)
        session.commit()
        service = AdminService(repository=SqlAlchemyAdminRepository(session), now=lambda: now, commit=session.commit, rollback=session.rollback)
        draft = service.create_catalog_draft(actor_user_id=actor.id, command=_draft_command(), command_key="create-publish-concurrent-0001")
        command = CatalogLifecycleCommand(reason="review complete", confirm=True)
        service.review_catalog_draft(actor_user_id=actor.id, draft_id=draft.id, expected_revision=1, command=command, command_key="review-publish-concurrent-0001")
        actor_id = actor.id
        draft_id = draft.id

    barrier = threading.Barrier(2)
    results: list[uuid.UUID] = []
    errors: list[BaseException] = []

    def publish() -> None:
        try:
            with Session(test_engine) as session:
                barrier.wait(timeout=5)
                response = AdminService(repository=SqlAlchemyAdminRepository(session), now=lambda: now, commit=session.commit, rollback=session.rollback).publish_catalog_draft(
                    actor_user_id=actor_id, draft_id=draft_id, expected_revision=1,
                    command=CatalogLifecycleCommand(reason="publish", confirm=True), command_key="publish-concurrent-0001",
                )
                results.append(response.id)
        except BaseException as error:  # pragma: no cover - assertion below reports thread failure
            errors.append(error)

    workers = [threading.Thread(target=publish) for _ in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=10)

    assert not errors
    assert len(results) == 2 and results[0] == results[1]
    with Session(test_engine) as session:
        assert session.scalar(select(CatalogActivePublication).where(CatalogActivePublication.draft_id == draft_id)).publication_id == results[0]
