"""Authoritative nutrition catalog ORM models sharing the application's Base."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.auth.models import Base


class NutritionCatalog(Base):
    """A named catalog family; seed import owns its records, never Alembic."""

    __tablename__ = "nutrition_catalogs"
    __table_args__ = (
        CheckConstraint(
            "catalog_key = btrim(catalog_key) AND catalog_key <> ''",
            name="ck_nutrition_catalogs_key",
        ),
        UniqueConstraint("catalog_key", name="uq_nutrition_catalogs_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    catalog_key: Mapped[str] = mapped_column(String(80), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    versions: Mapped[list["NutritionCatalogVersion"]] = relationship(
        back_populates="catalog", cascade="all, delete-orphan"
    )


class NutritionCatalogVersion(Base):
    """An immutable, versioned snapshot boundary for calculable nutrition data."""

    __tablename__ = "nutrition_catalog_versions"
    __table_args__ = (
        CheckConstraint(
            "version = btrim(version) AND version <> ''",
            name="ck_nutrition_catalog_versions_version",
        ),
        UniqueConstraint(
            "catalog_id", "version", name="uq_nutrition_catalog_versions_catalog_version"
        ),
        UniqueConstraint("content_hash", name="uq_nutrition_catalog_versions_content_hash"),
        Index("ix_nutrition_catalog_versions_catalog_released", "catalog_id", "released_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    catalog_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("nutrition_catalogs.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    released_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    catalog: Mapped[NutritionCatalog] = relationship(back_populates="versions")
    sources: Mapped[list["NutritionSource"]] = relationship(
        back_populates="catalog_version", cascade="all, delete-orphan"
    )
    foods: Mapped[list["FoodCatalogItem"]] = relationship(back_populates="catalog_version")


class NutritionSource(Base):
    """Traceable source and license for records in one catalog version."""

    __tablename__ = "nutrition_sources"
    __table_args__ = (
        CheckConstraint(
            "source_name = btrim(source_name) AND source_name <> ''",
            name="ck_nutrition_sources_name",
        ),
        CheckConstraint(
            "source_url = btrim(source_url) AND source_url <> ''",
            name="ck_nutrition_sources_url",
        ),
        CheckConstraint(
            "license_name = btrim(license_name) AND license_name <> ''",
            name="ck_nutrition_sources_license",
        ),
        UniqueConstraint(
            "catalog_version_id", "source_url", name="uq_nutrition_sources_version_url"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    catalog_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("nutrition_catalog_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_name: Mapped[str] = mapped_column(String(120), nullable=False)
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    license_name: Mapped[str] = mapped_column(String(120), nullable=False)

    catalog_version: Mapped[NutritionCatalogVersion] = relationship(back_populates="sources")
    foods: Mapped[list["FoodCatalogItem"]] = relationship(back_populates="source")


class FoodCatalogItem(Base):
    """One qualified food record linked to a version and its authoritative source."""

    __tablename__ = "food_catalog_items"
    __table_args__ = (
        CheckConstraint(
            "stable_id = btrim(stable_id) AND stable_id <> ''",
            name="ck_food_catalog_items_stable_id",
        ),
        CheckConstraint(
            "canonical_name = btrim(canonical_name) AND canonical_name <> ''",
            name="ck_food_catalog_items_canonical_name",
        ),
        CheckConstraint(
            "prepared_state = btrim(prepared_state) AND prepared_state <> ''",
            name="ck_food_catalog_items_prepared_state",
        ),
        CheckConstraint(
            "NOT is_qualified OR (energy_kcal_per_100g IS NOT NULL AND protein_g_per_100g IS NOT NULL AND fat_g_per_100g IS NOT NULL AND carbohydrate_g_per_100g IS NOT NULL)",
            name="ck_food_catalog_items_qualified_nutrients",
        ),
        UniqueConstraint(
            "catalog_version_id", "stable_id", name="uq_food_catalog_version_stable_id"
        ),
        Index("ix_food_catalog_items_version_name", "catalog_version_id", "canonical_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    catalog_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("nutrition_catalog_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("nutrition_sources.id", ondelete="RESTRICT"), nullable=False
    )
    stable_id: Mapped[str] = mapped_column(String(120), nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(200), nullable=False)
    prepared_state: Mapped[str] = mapped_column(String(120), nullable=False)
    is_qualified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    energy_kcal_per_100g: Mapped[Decimal | None] = mapped_column(Numeric(14, 6))
    protein_g_per_100g: Mapped[Decimal | None] = mapped_column(Numeric(14, 6))
    fat_g_per_100g: Mapped[Decimal | None] = mapped_column(Numeric(14, 6))
    carbohydrate_g_per_100g: Mapped[Decimal | None] = mapped_column(Numeric(14, 6))

    aliases: Mapped[list[FoodCatalogAlias]] = relationship(
        back_populates="food", cascade="all, delete-orphan"
    )
    portions: Mapped[list[FoodCatalogPortion]] = relationship(
        back_populates="food", cascade="all, delete-orphan"
    )
    catalog_version: Mapped[NutritionCatalogVersion] = relationship(back_populates="foods")
    source: Mapped[NutritionSource] = relationship(back_populates="foods")


class FoodCatalogAlias(Base):
    __tablename__ = "food_catalog_aliases"
    __table_args__ = (
        CheckConstraint(
            "alias = btrim(alias) AND alias <> ''", name="ck_food_catalog_aliases_alias"
        ),
        CheckConstraint(
            "normalized_alias = btrim(normalized_alias) AND normalized_alias <> ''",
            name="ck_food_catalog_aliases_normalized_alias",
        ),
        UniqueConstraint("food_id", "normalized_alias", name="uq_food_alias_per_food"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    food_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("food_catalog_items.id", ondelete="CASCADE"), nullable=False
    )
    alias: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    is_controlled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    food: Mapped[FoodCatalogItem] = relationship(back_populates="aliases")


class FoodCatalogPortion(Base):
    __tablename__ = "food_catalog_portions"
    __table_args__ = (
        CheckConstraint(
            "description = btrim(description) AND description <> ''",
            name="ck_food_catalog_portions_description",
        ),
        CheckConstraint("grams > 0", name="ck_food_catalog_portions_grams_positive"),
        CheckConstraint(
            "source_reference = btrim(source_reference) AND source_reference <> ''",
            name="ck_food_catalog_portions_source_reference",
        ),
        CheckConstraint(
            "version = btrim(version) AND version <> ''",
            name="ck_food_catalog_portions_version",
        ),
        UniqueConstraint("food_id", "description", name="uq_food_catalog_portions_food_description"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    food_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("food_catalog_items.id", ondelete="CASCADE"), nullable=False
    )
    description: Mapped[str] = mapped_column(String(120), nullable=False)
    grams: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    source_reference: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    audited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    food: Mapped[FoodCatalogItem] = relationship(back_populates="portions")
