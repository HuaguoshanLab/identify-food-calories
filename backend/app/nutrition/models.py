"""Authoritative nutrition catalog ORM models sharing the application's Base."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.auth.models import Base


class FoodCatalogItem(Base):
    """One versioned, sourced, calculable food record; persisted via a later migration."""

    __tablename__ = "food_catalog_items"
    __table_args__ = (
        UniqueConstraint("stable_id", "catalog_version", name="uq_food_catalog_stable_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    stable_id: Mapped[str] = mapped_column(String(120), nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(200), nullable=False)
    catalog_version: Mapped[str] = mapped_column(String(80), nullable=False)
    prepared_state: Mapped[str] = mapped_column(String(120), nullable=False)
    source_name: Mapped[str] = mapped_column(String(120), nullable=False)
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    license_name: Mapped[str] = mapped_column(String(120), nullable=False)
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


class FoodCatalogAlias(Base):
    __tablename__ = "food_catalog_aliases"
    __table_args__ = (
        UniqueConstraint("food_id", "normalized_alias", name="uq_food_alias_per_food"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    food_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("food_catalog_items.id", ondelete="CASCADE"), nullable=False
    )
    alias: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    is_controlled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    food: Mapped[FoodCatalogItem] = relationship(back_populates="aliases")


class FoodCatalogPortion(Base):
    __tablename__ = "food_catalog_portions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    food_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("food_catalog_items.id", ondelete="CASCADE"), nullable=False
    )
    description: Mapped[str] = mapped_column(String(120), nullable=False)
    grams: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    source_reference: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    audited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    food: Mapped[FoodCatalogItem] = relationship(back_populates="portions")
