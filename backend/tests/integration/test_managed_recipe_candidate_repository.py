"""PostgreSQL eligibility contracts for managed recipe candidates."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import uuid

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.nutrition.models import FoodCatalogItem, NutritionCatalog, NutritionCatalogVersion, NutritionSource
from app.nutrition.repository import SqlAlchemyNutritionRepository
from app.nutrition.service import NutritionService
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
from app.planning.schemas import MealSlot, PlanValidationAction, PreferenceReview
from app.planning.service import PlanningService


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


@pytest.mark.parametrize("deleted", [False, True])
def test_disabled_or_deleted_pool_prevents_bootstrap_recipe_fallback(db_session, deleted):
    db_session.execute(delete(ManagedRecipeCandidate))
    repository = SqlAlchemyPlanningProfileRepository(db_session)
    assert repository.has_managed_recipe_candidates() is False
    row = _candidate(_catalog_item(db_session), status="disabled", deleted_at=datetime.now(UTC) if deleted else None)
    db_session.add(row)
    db_session.flush()
    assert repository.has_managed_recipe_candidates() is True
    assert repository.list_managed_recipe_candidates(catalog_version=None) == []
    result = PlanningService(repository=repository, nutrition_port=NutritionService(repository=SqlAlchemyNutritionRepository(db_session))).compose_daily_meals(catalog_version=None, preferences=PreferenceReview(confirmed=True))
    assert result.action is PlanValidationAction.REPLAN


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


def _planning_service(session: Session) -> PlanningService:
    return PlanningService(
        repository=SqlAlchemyPlanningProfileRepository(session),
        nutrition_port=NutritionService(repository=SqlAlchemyNutritionRepository(session)),
    )


def _replaceable(service: PlanningService, identity, *, exclusions=(), exclude_recipe_ids=()):
    return service.keep_replaceable_food_identities(
        identities=(identity,), affected_slot=MealSlot.LUNCH,
        exclude_recipe_ids=exclude_recipe_ids,
        preferences=PreferenceReview(confirmed=True, exclusions=exclusions),
    )


@pytest.mark.parametrize("condition", [
    "no_recipe", "wrong_slot", "disabled", "deleted", "stale_version",
    "disqualified", "retired_publication", "excluded_food", "current_recipe", "component",
])
def test_replacement_filters_unusable_catalog_hits_in_postgresql(db_session, condition) -> None:
    recipe = _published_candidate(db_session)
    identity = (recipe.catalog_publication_id, recipe.nutrition_catalog_version)
    service = _planning_service(db_session)
    assert _replaceable(service, identity) == (identity,)

    exclusions = ()
    excluded_ids = ()
    if condition == "no_recipe":
        db_session.delete(recipe)
    elif condition == "wrong_slot":
        recipe.meal_slot = "breakfast"
    elif condition == "component":
        recipe.meal_role = "vegetable"
    elif condition == "disabled":
        recipe.status = "disabled"
    elif condition == "deleted":
        recipe.deleted_at = datetime.now(UTC)
    elif condition == "stale_version":
        recipe.nutrition_catalog_version = "admin-publication-stale"
    elif condition == "disqualified":
        db_session.add(CatalogPublicationEligibility(
            id=uuid.uuid4(), publication_id=identity[0], status="disqualified",
            actor_identifier="test", reason="test revocation",
            command_key=f"revoke-{uuid.uuid4().hex}", occurred_at=datetime.now(UTC),
        ))
    elif condition == "retired_publication":
        db_session.execute(delete(CatalogActivePublication).where(
            CatalogActivePublication.publication_id == identity[0]
        ))
    elif condition == "excluded_food":
        exclusions = (recipe.catalog_food_name,)
    elif condition == "current_recipe":
        excluded_ids = (recipe.id,)
    db_session.flush()

    assert _replaceable(service, identity, exclusions=exclusions, exclude_recipe_ids=excluded_ids) == ()
    if condition == "no_recipe":
        # A valid nutrition hit alone does not make a planning replacement usable.
        assert SqlAlchemyNutritionRepository(db_session).get_qualified_food(
            food_id=identity[0], catalog_version=identity[1]
        ) is not None


def _additional_recipe(session, original, slot):
    recipe = ManagedRecipeCandidate(
        id=uuid.uuid4(), catalog_publication_id=original.catalog_publication_id,
        catalog_food_name=original.catalog_food_name,
        nutrition_catalog_version=original.nutrition_catalog_version,
        meal_slot=slot, portion_grams=Decimal("100"), portion_description="一份",
        method_tags="蒸", flavour_tags="清淡", status="enabled", revision=1,
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )
    session.add(recipe)
    session.flush()
    return recipe


def test_multiple_recipes_keep_one_food_candidate_and_recompute_selected_portion(db_session) -> None:
    first = _published_candidate(db_session)
    alternate = _additional_recipe(db_session, first, "lunch")
    _additional_recipe(db_session, first, "breakfast")
    _additional_recipe(db_session, first, "dinner")
    service = _planning_service(db_session)
    identity = (first.catalog_publication_id, first.nutrition_catalog_version)

    assert _replaceable(service, identity) == (identity,)
    assert _replaceable(service, identity, exclude_recipe_ids=(first.id,)) == (identity,)
    result = service.compose_daily_meals(
        catalog_version=None, preferences=PreferenceReview(confirmed=True),
        exclude_recipe_ids=(first.id,), required_food_id=identity[0],
        required_catalog_version=identity[1], required_slot=MealSlot.LUNCH,
    )

    assert result.action is PlanValidationAction.PASS
    lunch = next(meal for meal in result.meals if meal.slot is MealSlot.LUNCH)
    assert lunch.recipe_id == alternate.id
    assert lunch.portion_grams == Decimal("100")
    assert lunch.nutrients.energy_kcal == Decimal("130")


def test_admin_disable_between_candidate_offer_and_confirmation_is_reread(test_engine) -> None:
    """Two committed connections model an admin update while selection is pending."""
    with Session(test_engine) as setup:
        recipe = _published_candidate(setup)
        _additional_recipe(setup, recipe, "breakfast")
        _additional_recipe(setup, recipe, "dinner")
        recipe_id = recipe.id
        identity = (recipe.catalog_publication_id, recipe.nutrition_catalog_version)
        publication = setup.get(CatalogPublication, identity[0])
        draft_id, review_id = publication.draft_id, publication.review_id
        setup.commit()

    try:
        with Session(test_engine) as reader:
            service = _planning_service(reader)
            arguments = dict(
                catalog_version=None, preferences=PreferenceReview(confirmed=True),
                required_food_id=identity[0], required_catalog_version=identity[1],
                required_slot=MealSlot.LUNCH,
            )
            assert _replaceable(service, identity) == (identity,)
            assert service.compose_daily_meals(**arguments).action is PlanValidationAction.PASS
            with Session(test_engine) as administrator:
                administrator.execute(update(ManagedRecipeCandidate).where(
                    ManagedRecipeCandidate.id == recipe_id
                ).values(status="disabled", revision=2, updated_at=datetime.now(UTC)))
                administrator.commit()

            assert _replaceable(service, identity) == ()
            result = service.compose_daily_meals(**arguments)
            assert result.action is PlanValidationAction.REPLAN
            assert result.meals == ()
    finally:
        # Committed fixtures need explicit, ID-scoped cleanup across both connections.
        with Session(test_engine) as cleanup:
            cleanup.execute(delete(ManagedRecipeCandidate).where(
                ManagedRecipeCandidate.catalog_publication_id == identity[0]
            ))
            cleanup.execute(delete(CatalogActivePublication).where(CatalogActivePublication.draft_id == draft_id))
            cleanup.execute(delete(CatalogPublicationEligibility).where(
                CatalogPublicationEligibility.publication_id == identity[0]
            ))
            cleanup.execute(delete(CatalogPublication).where(CatalogPublication.id == identity[0]))
            cleanup.execute(delete(CatalogDraftReview).where(CatalogDraftReview.id == review_id))
            cleanup.execute(delete(CatalogDraft).where(CatalogDraft.id == draft_id))
            cleanup.commit()
            assert cleanup.scalar(select(ManagedRecipeCandidate.id).where(
                ManagedRecipeCandidate.catalog_publication_id == identity[0]
            )) is None


def test_explicit_recipe_selection_is_version_bound_and_never_falls_back(db_session):
    first = _published_candidate(db_session)
    chosen = _additional_recipe(db_session, first, "lunch")
    _additional_recipe(db_session, first, "breakfast")
    _additional_recipe(db_session, first, "dinner")
    service = _planning_service(db_session)
    arguments = dict(
        catalog_version=None, preferences=PreferenceReview(confirmed=True),
        required_food_id=first.catalog_publication_id,
        required_catalog_version=first.nutrition_catalog_version,
        required_slot=MealSlot.LUNCH, required_recipe_id=chosen.id,
        required_recipe_revision=chosen.revision,
    )
    offered = service.list_replacement_recipes(
        food_id=first.catalog_publication_id, catalog_version=first.nutrition_catalog_version,
        affected_slot=MealSlot.LUNCH, exclude_recipe_ids=(), preferences=PreferenceReview(confirmed=True),
    )
    assert {item.id for item in offered} == {first.id, chosen.id}
    result = service.compose_daily_meals(**arguments)
    assert result.action is PlanValidationAction.PASS
    assert next(meal for meal in result.meals if meal.slot is MealSlot.LUNCH).recipe_id == chosen.id
    chosen.revision += 1
    db_session.flush()
    assert service.compose_daily_meals(**arguments).action is PlanValidationAction.NEEDS_INPUT
    arguments["required_recipe_revision"] = chosen.revision
    chosen.status = "disabled"
    db_session.flush()
    refused = service.compose_daily_meals(**arguments)
    assert refused.action is PlanValidationAction.NEEDS_INPUT
    assert refused.meals == ()


def test_keyset_pages_merge_catalog_sources_filter_slots_and_recheck_eligibility(db_session):
    from sqlalchemy import event
    db_session.execute(delete(ManagedRecipeCandidate))
    item = _catalog_item(db_session)
    first = _candidate(item)
    first.id = uuid.UUID(int=1)
    other_slot = _candidate(item)
    other_slot.meal_slot = "dinner"
    other_slot.id = uuid.UUID(int=2)
    disabled = _candidate(item, status="disabled")
    disabled.id = uuid.UUID(int=3)
    later = _candidate(item)
    later.id = uuid.UUID(int=5)
    db_session.add_all([first, other_slot, disabled, later])
    published = _published_candidate(db_session)
    published.id = uuid.UUID(int=4)
    published.meal_slot = "breakfast"
    db_session.flush()
    repo = SqlAlchemyPlanningProfileRepository(db_session)
    sql = []
    def capture(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().startswith("SELECT") and "managed_recipe_candidates" in statement:
            sql.append(statement)
    connection = db_session.connection()
    event.listen(connection, "before_cursor_execute", capture)
    try:
        page1 = repo.list_managed_recipe_candidates(catalog_version=None, meal_slot=MealSlot.BREAKFAST, limit=1)
        assert [row.id for row in page1] == [first.id]
        # Updated timestamps cannot move a visited row across the UUID cursor.
        first.updated_at = datetime.now(UTC)
        db_session.flush()
        page2 = repo.list_managed_recipe_candidates(catalog_version=None, meal_slot=MealSlot.BREAKFAST, after_id=page1[-1].id, limit=1)
        assert [row.id for row in page2] == [published.id]
        later.status = "disabled"
        db_session.flush()
        assert repo.list_managed_recipe_candidates(catalog_version=None, meal_slot=MealSlot.BREAKFAST, after_id=page2[-1].id, limit=1) == []
        assert all("LIMIT" in statement and "OFFSET" not in statement for statement in sql)
        assert repo.list_managed_recipe_candidates(catalog_version=None, meal_slot=MealSlot.BREAKFAST, food_ids=(published.catalog_publication_id,), recipe_id=published.id, recipe_revision=published.revision, limit=1)[0].id == published.id
        assert repo.list_managed_recipe_candidates(catalog_version=None, meal_slot=MealSlot.BREAKFAST, recipe_id=published.id, recipe_revision=published.revision + 1, limit=1) == []
    finally:
        event.remove(connection, "before_cursor_execute", capture)


def test_large_real_catalog_composes_using_bounded_database_pages(db_session):
    from sqlalchemy import event
    from app.planning.selection import PlanningSearchBudget
    db_session.execute(delete(ManagedRecipeCandidate))
    published = _published_candidate(db_session)
    for index in range(1200):
        row = ManagedRecipeCandidate(
            id=uuid.UUID(int=index + 1), food_catalog_item_id=None,
            catalog_publication_id=published.catalog_publication_id,
            catalog_food_name=published.catalog_food_name,
            nutrition_catalog_version=published.nutrition_catalog_version,
            portion_grams=published.portion_grams, portion_description=published.portion_description,
            method_tags=published.method_tags, flavour_tags=published.flavour_tags,
            status="enabled", revision=1, created_at=published.created_at, updated_at=published.updated_at,
        )
        row.meal_slot = ("breakfast", "lunch", "dinner")[index % 3]
        db_session.add(row)
    db_session.flush()
    page_sizes = []
    repo = SqlAlchemyPlanningProfileRepository(db_session)
    original = repo.list_managed_recipe_candidates
    def read_page(**kwargs):
        result = original(**kwargs)
        page_sizes.append(len(result))
        return result
    repo.list_managed_recipe_candidates = read_page
    queries = []
    connection = db_session.connection()
    def capture(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().startswith("SELECT") and "managed_recipe_candidates.id IN" in statement:
            queries.append(statement)
    event.listen(connection, "before_cursor_execute", capture)
    try:
        service = PlanningService(repository=repo, nutrition_port=NutritionService(repository=SqlAlchemyNutritionRepository(db_session)), search_budget=PlanningSearchBudget(batch_size=7, scan_per_slot=10))
        result = service.compose_daily_meals(catalog_version=None, preferences=PreferenceReview(confirmed=True))
        assert result.action is PlanValidationAction.PASS
        assert {meal.slot for meal in result.meals} == {MealSlot.BREAKFAST, MealSlot.LUNCH, MealSlot.DINNER}
        assert page_sizes == [7, 3, 7, 3, 7, 3]
        assert len(queries) == 6
        assert all("LIMIT" in statement for statement in queries)
    finally:
        event.remove(connection, "before_cursor_execute", capture)


@pytest.mark.parametrize("source", ["imported", "published"])
def test_component_roles_are_filtered_before_pagination_and_explicit_selection(db_session, source):
    db_session.execute(delete(ManagedRecipeCandidate))
    if source == "published":
        component = _published_candidate(db_session)
        standalone = _additional_recipe(db_session, component, "lunch")
    else:
        food = _catalog_item(db_session)
        component, standalone = _candidate(food), _candidate(food)
        component.meal_slot = standalone.meal_slot = "lunch"
        db_session.add_all((component, standalone))
    component.id = uuid.UUID(int=1)
    standalone.id = uuid.UUID(int=2)
    component.meal_role = "vegetable"
    db_session.flush()
    assert standalone.meal_role == "standalone"
    repo = SqlAlchemyPlanningProfileRepository(db_session)
    assert repo.has_managed_recipe_candidates()
    page = repo.list_managed_recipe_candidates(catalog_version=None, meal_slot=MealSlot.LUNCH, limit=1)
    assert [row.id for row in page] == [standalone.id]
    assert page[0].meal_role == "standalone"
    assert repo.list_managed_recipe_candidates(catalog_version=None, recipe_id=component.id) == []
    standalone.meal_role = "drink"
    db_session.flush()
    assert repo.list_managed_recipe_candidates(catalog_version=None) == []
    assert repo.has_managed_recipe_candidates()  # Do not reactivate bootstrap recipes.


def test_postgres_rejects_unknown_roles(db_session):
    from sqlalchemy.exc import IntegrityError
    candidate = _candidate(_catalog_item(db_session))
    db_session.add(candidate)
    db_session.flush()
    with pytest.raises(IntegrityError), db_session.begin_nested():
        candidate.meal_role = "invented"
        db_session.flush()


def test_role_migration_roundtrip_preserves_candidates_and_backfills_legacy_rows(db_session):
    import importlib
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect, text

    row = _candidate(_catalog_item(db_session))
    row.meal_role = "side"
    db_session.add(row)
    db_session.flush()
    connection = db_session.connection()
    migration = importlib.import_module("migrations.versions.0029_recipe_meal_role")
    # DDL stays inside the isolated fixture transaction; no committed data is altered.
    with Operations.context(MigrationContext.configure(connection)):
        migration.downgrade()
        assert "meal_role" not in {column["name"] for column in inspect(connection).get_columns("managed_recipe_candidates")}
        migration.upgrade()
    assert connection.execute(text("SELECT meal_role, revision FROM managed_recipe_candidates WHERE id = :id"), {"id": row.id}).one() == ("standalone", 1)


def test_explicit_components_generate_real_calculated_meals_in_postgres(db_session):
    from tests.planning.test_meal_bundles import fixtures
    db_session.execute(delete(ManagedRecipeCandidate))
    foods, candidates, target = fixtures(alternatives=2)
    food_map = {}
    # The calculator accepts only the current governed catalog, not arbitrary
    # imported versions. Keep all fixture foods in that one authoritative version.
    anchor = _catalog_item(db_session)
    version = db_session.get(NutritionCatalogVersion, anchor.catalog_version_id)
    catalog = db_session.scalar(select(NutritionCatalog).where(NutritionCatalog.catalog_key == "reference-recipes"))
    if catalog is None:
        catalog = db_session.get(NutritionCatalog, version.catalog_id)
        catalog.catalog_key = "reference-recipes"
    else:
        version.catalog_id = catalog.id
    for food in foods:
        item = anchor if not food_map else FoodCatalogItem(
            id=uuid.uuid4(), catalog_version_id=anchor.catalog_version_id,
            source_id=anchor.source_id, stable_id=uuid.uuid4().hex,
            canonical_name=food.canonical_name, prepared_state="cooked", is_qualified=True,
        )
        db_session.add(item)
        item.canonical_name = food.canonical_name
        for metric, value in food.nutrients_per_100g.model_dump().items():
            setattr(item, f"{metric}_per_100g", value)
        food_map[food.id] = item
    for candidate in candidates:
        row = _candidate(food_map[candidate.nutrition_item_id])
        row.meal_slot = candidate.meal_slot.value
        row.meal_role = candidate.meal_role
        row.portion_grams = candidate.portion_grams
        db_session.add(row)
    db_session.flush()
    repo = SqlAlchemyPlanningProfileRepository(db_session)
    assert len(repo.list_managed_recipe_candidates(catalog_version=None)) == 1
    assert len(repo.list_managed_recipe_candidates(catalog_version=None, include_components=True)) == len(candidates)
    result = _planning_service(db_session).compose_daily_meals(catalog_version=None, target=target, preferences=PreferenceReview(confirmed=True))
    assert result.action is PlanValidationAction.PASS
    assert [len(meal.items) for meal in result.meals] == [0, 3, 3]
    assert result.meals[1].nutrients.energy_kcal == Decimal('540')
    # Current qualification, not the administrator's role label, controls eligibility.
    for candidate in candidates:
        if candidate.meal_role == 'vegetable':
            food_map[candidate.nutrition_item_id].is_qualified = False
    db_session.flush()
    failure = _planning_service(db_session).compose_daily_meals(catalog_version=None, target=target, preferences=PreferenceReview(confirmed=True))
    assert failure.action is PlanValidationAction.REPLAN and failure.meals == ()
