"""PostgreSQL eligibility contracts for managed recipe candidates."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import uuid

from app.nutrition.models import FoodCatalogItem, NutritionCatalog, NutritionCatalogVersion, NutritionSource
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
        portion_description="一盘", method_tags="炒", flavour_tags="家常", status=status, revision=1,
        created_at=now, updated_at=now, deleted_at=deleted_at,
    )


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

    candidates = SqlAlchemyPlanningProfileRepository(db_session).list_managed_recipe_candidates(
        catalog_version="managed-test.v1"
    )

    assert [candidate.food_catalog_item_id for candidate in candidates] == [qualified.id]
