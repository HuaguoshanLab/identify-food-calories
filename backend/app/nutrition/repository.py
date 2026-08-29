"""Flush-only SQLAlchemy adapter for the nutrition repository port."""

from __future__ import annotations

import uuid

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app.nutrition.models import (
    FoodCatalogAlias,
    FoodCatalogPortion,
    FoodCatalogItem,
    NutritionCatalog,
    NutritionCatalogVersion,
    NutritionSource,
)
from app.nutrition.importer import CatalogManifest, ImportedCatalogVersion
from app.nutrition.schemas import ControlledPortion, NutritionValues, QualifiedFood


class SqlAlchemyNutritionRepository:
    """Query adapter; services own commit and rollback boundaries if writes are added."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def search_qualified_foods(self, *, normalized_query: str, limit: int) -> list[QualifiedFood]:
        statement = (
            self._qualified_statement()
            .join(FoodCatalogAlias)
            .where(FoodCatalogAlias.normalized_alias.contains(normalized_query))
            .order_by(FoodCatalogAlias.normalized_alias, FoodCatalogItem.canonical_name)
            .limit(limit)
        )
        return [self._to_qualified_food(row) for row in self._session.scalars(statement).unique()]

    def get_qualified_food(
        self, *, food_id: uuid.UUID, catalog_version: str
    ) -> QualifiedFood | None:
        statement = self._qualified_statement().where(
            FoodCatalogItem.id == food_id,
            NutritionCatalogVersion.version == catalog_version,
        )
        item = self._session.scalar(statement)
        return self._to_qualified_food(item) if item is not None else None

    @staticmethod
    def _qualified_statement() -> Select[tuple[FoodCatalogItem]]:
        return (
            select(FoodCatalogItem)
            .options(
                selectinload(FoodCatalogItem.aliases),
                selectinload(FoodCatalogItem.portions),
                selectinload(FoodCatalogItem.catalog_version),
                selectinload(FoodCatalogItem.source),
            )
            .join(NutritionCatalogVersion)
            .join(NutritionSource)
            .where(
                FoodCatalogItem.is_qualified.is_(True),
                FoodCatalogItem.energy_kcal_per_100g.is_not(None),
                FoodCatalogItem.protein_g_per_100g.is_not(None),
                FoodCatalogItem.fat_g_per_100g.is_not(None),
                FoodCatalogItem.carbohydrate_g_per_100g.is_not(None),
            )
        )

    @staticmethod
    def _to_qualified_food(item: FoodCatalogItem) -> QualifiedFood:
        # The SQL predicate is the qualification boundary; the assertions retain the
        # type-level promise if a future adapter accidentally weakens that predicate.
        assert item.energy_kcal_per_100g is not None
        assert item.protein_g_per_100g is not None
        assert item.fat_g_per_100g is not None
        assert item.carbohydrate_g_per_100g is not None
        return QualifiedFood(
            id=item.id,
            canonical_name=item.canonical_name,
            catalog_version=item.catalog_version.version,
            prepared_state=item.prepared_state,
            source_name=item.source.source_name,
            source_url=item.source.source_url,
            license_name=item.source.license_name,
            aliases=tuple(alias.alias for alias in item.aliases if alias.is_controlled),
            portions=tuple(
                ControlledPortion(
                    description=portion.description,
                    grams=portion.grams,
                    source_reference=portion.source_reference,
                    version=portion.version,
                    audited=portion.audited,
                )
                for portion in item.portions
                if portion.audited
            ),
            nutrients_per_100g=NutritionValues(
                energy_kcal=item.energy_kcal_per_100g,
                protein_g=item.protein_g_per_100g,
                fat_g=item.fat_g_per_100g,
                carbohydrate_g=item.carbohydrate_g_per_100g,
            ),
        )


class SqlAlchemyNutritionCatalogImportRepository:
    """Flush-only adapter for the catalog import service.

    Seed data belongs to the immutable catalog lifecycle, not to Alembic.  Keeping
    these writes here prevents the CLI from obtaining an unbounded ORM session.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_imported_version(
        self, *, catalog_key: str, version: str
    ) -> ImportedCatalogVersion | None:
        row = self._session.scalar(
            select(NutritionCatalogVersion)
            .join(NutritionCatalog)
            .where(NutritionCatalog.catalog_key == catalog_key, NutritionCatalogVersion.version == version)
        )
        if row is None:
            return None
        return ImportedCatalogVersion(version=row.version, content_hash=row.content_hash)

    def add_manifest(self, manifest: CatalogManifest) -> None:
        catalog = self._session.scalar(
            select(NutritionCatalog).where(NutritionCatalog.catalog_key == manifest.catalog_key)
        )
        if catalog is None:
            catalog = NutritionCatalog(
                catalog_key=manifest.catalog_key,
                display_name=manifest.catalog_display_name,
                created_at=manifest.released_at,
            )
            self._session.add(catalog)
            self._session.flush()

        version = NutritionCatalogVersion(
            catalog_id=catalog.id,
            version=manifest.version,
            content_hash=manifest.content_hash,
            released_at=manifest.released_at,
        )
        self._session.add(version)
        self._session.flush()
        for food in manifest.foods:
            source = NutritionSource(
                catalog_version_id=version.id,
                source_name=manifest.provenance.source_name,
                source_url=food.source_url,
                license_name=manifest.provenance.license_name,
            )
            self._session.add(source)
            self._session.flush()
            item = FoodCatalogItem(
                catalog_version_id=version.id,
                source_id=source.id,
                stable_id=food.stable_id,
                canonical_name=food.canonical_name,
                prepared_state=food.prepared_state,
                is_qualified=food.is_qualified,
                energy_kcal_per_100g=food.nutrients_per_100g.energy_kcal,
                protein_g_per_100g=food.nutrients_per_100g.protein_g,
                fat_g_per_100g=food.nutrients_per_100g.fat_g,
                carbohydrate_g_per_100g=food.nutrients_per_100g.carbohydrate_g,
            )
            self._session.add(item)
            self._session.flush()
            self._session.add_all(
                FoodCatalogAlias(
                    food_id=item.id,
                    alias=alias,
                    normalized_alias=alias.casefold().strip(),
                    is_controlled=True,
                )
                for alias in food.aliases
            )
            self._session.add_all(
                FoodCatalogPortion(
                    food_id=item.id,
                    description=portion.description,
                    grams=portion.grams,
                    source_reference=portion.source_reference,
                    version=portion.version,
                    audited=portion.audited,
                )
                for portion in food.portions
            )
        self._session.flush()
