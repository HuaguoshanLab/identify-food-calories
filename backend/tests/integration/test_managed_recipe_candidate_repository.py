"""PostgreSQL eligibility contracts for managed recipe candidates."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import uuid

from app.nutrition.models import FoodCatalogItem, NutritionCatalog, NutritionCatalogVersion, NutritionSource
from app.admin.models import (
    CatalogActivePublication,
    CatalogDraft,
    CatalogDraftReview,
    CatalogPublication,
    CatalogPublicationEligibility,
)
from app.admin.repository import SqlAlchemyAdminRepository
from app.planning.models import ManagedRecipeCandidate
from app.planning.repository import SqlAlchemyPlanningProfileRepository


def _catalog_item(db_session, *, qualified: bool = True, complete_nutrients: bool = True) -> FoodCatalogItem:
    now = datetime.now(UTC)
    catalog = NutritionCatalog(id=uuid.uuid4(), catalog_key=f"managed-test-{uuid.uuid4().hex}", display_name="test", created_at=now)
    version = NutritionCatalogVersion(id=uuid.uuid4(), catalog_id=catalog.id, version="managed-test.v1", released_at=now, content_hash=uuid.uuid4().hex + uuid.uuid4().hex)
    source = NutritionSource(id=uuid.uuid4(), catalog_version_id=version.id, source_name="test", source_url=f"https://example.test/{uuid.uuid4()}", license_name="test")
    item = FoodCatalogItem(
        id=uuid.uuid4(), catalog_version_id=version.id, source_id=source.id, stable_id=f"food-{uuid.uuid4().hex}", canonical_name="候选菜",
        prepared_state="cooked", is_qualified=qualified and complete_nutrients,
        energy_kcal_per_100g=Decimal("100") if complete_nutrients else None,
        protein_g_per_100g=Decimal("10"), fat_g_per_100g=Decimal("5"), carbohydrate_g_per_100g=Decimal("10"),
    )
    db_session.add_all((catalog, version, source, item))
    db_session.flush()
    return item


def _candidate(item: FoodCatalogItem, *, status: str = "enabled", deleted_at=None) -> ManagedRecipeCandidate:
    now = datetime.now(UTC)
    return ManagedRecipeCandidate(
        id=uuid.uuid4(), food_catalog_item_id=item.id, meal_slot="breakfast", portion_grams=Decimal("180"),
        catalog_publication_id=None, catalog_food_name=item.canonical_name,
        nutrition_catalog_version="managed-test.v1",
        portion_description="一盘", method_tags="炒", flavour_tags="家常", status=status, revision=1,
        created_at=now, updated_at=now, deleted_at=deleted_at,
    )


def _published_candidate(db_session, *, canonical_name: str | None = None) -> ManagedRecipeCandidate:
    now = datetime.now(UTC)
    suffix = uuid.uuid4().hex
    draft = CatalogDraft(
        id=uuid.uuid4(), canonical_name=canonical_name or f"后台发布目录菜-{suffix}", aliases=[f"发布别名-{suffix}"],
        energy_kcal_per_100g=Decimal("130"), protein_g_per_100g=Decimal("12"),
        fat_g_per_100g=Decimal("7"), carbohydrate_g_per_100g=Decimal("15"),
        source_name="test", source_url=f"https://example.test/{suffix}",
        authorization_status="authorized", revision=1, created_at=now, updated_at=now,
    )
    snapshot = {
        "canonical_name": draft.canonical_name, "aliases": draft.aliases,
        "energy_kcal_per_100g": "130", "protein_g_per_100g": "12",
        "fat_g_per_100g": "7", "carbohydrate_g_per_100g": "15",
        "source_name": draft.source_name, "source_url": draft.source_url,
    }
    review = CatalogDraftReview(
        id=uuid.uuid4(), draft_id=draft.id, draft_revision=1, snapshot=snapshot,
        content_hash=uuid.uuid4().hex, actor_identifier="test", reason="test",
        command_key=f"review-{suffix}", reviewed_at=now,
    )
    publication = CatalogPublication(
        id=uuid.uuid4(), draft_id=draft.id, review_id=review.id, draft_revision=1,
        snapshot=snapshot, content_hash=uuid.uuid4().hex, actor_identifier="test",
        reason="test", command_key=f"publish-{suffix}", published_at=now,
    )
    db_session.add(draft)
    db_session.flush()
    db_session.add(review)
    db_session.flush()
    db_session.add(publication)
    db_session.flush()
    db_session.add_all((
        CatalogActivePublication(draft_id=draft.id, publication_id=publication.id, advanced_at=now),
        CatalogPublicationEligibility(
            id=uuid.uuid4(), publication_id=publication.id, status="eligible",
            actor_identifier="test", reason="test", command_key=f"eligible-{suffix}", occurred_at=now,
        ),
    ))
    db_session.flush()
    candidate = ManagedRecipeCandidate(
        id=uuid.uuid4(), food_catalog_item_id=None,
        catalog_publication_id=publication.id, catalog_food_name=draft.canonical_name,
        nutrition_catalog_version="admin-publication-v1", meal_slot="lunch",
        portion_grams=Decimal("180"), portion_description="一份", method_tags="炒",
        flavour_tags="家常", status="enabled", revision=1,
        created_at=now, updated_at=now,
    )
    db_session.add(candidate)
    db_session.flush()
    return candidate


def test_repository_only_returns_enabled_candidates_linked_to_current_qualified_catalog_items(db_session) -> None:
    qualified = _catalog_item(db_session)
    disabled = _catalog_item(db_session)
    unqualified = _catalog_item(db_session, qualified=False)
    missing_nutrients = _catalog_item(db_session, complete_nutrients=False)
    deleted = _catalog_item(db_session)
    now = datetime.now(UTC)
    db_session.add_all((
        _candidate(qualified), _candidate(disabled, status="disabled"), _candidate(unqualified),
        _candidate(missing_nutrients), _candidate(deleted, deleted_at=now),
    ))
    db_session.flush()

    published = _published_candidate(db_session)
    candidates = SqlAlchemyPlanningProfileRepository(db_session).list_managed_recipe_candidates(
        catalog_version=None
    )

    assert [(candidate.nutrition_item_id, candidate.catalog_version) for candidate in candidates] == [
        (qualified.id, "managed-test.v1"),
        (published.catalog_publication_id, "admin-publication-v1"),
    ]


def test_admin_lookup_collapses_exact_duplicate_published_nutrition_records(db_session) -> None:
    first = _published_candidate(db_session, canonical_name="重复发布菜")
    second = _published_candidate(db_session, canonical_name="重复发布菜")

    resolved = SqlAlchemyAdminRepository(db_session).resolve_qualified_food_by_name("重复发布菜")

    assert len(resolved) == 1
    assert resolved[0].id == min(
        first.catalog_publication_id, second.catalog_publication_id, key=str
    )
