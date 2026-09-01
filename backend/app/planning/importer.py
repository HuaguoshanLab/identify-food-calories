"""Offline importer for the project's short, auditable controlled-recipe seed."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import Settings, validate_test_database_configuration
from app.nutrition.models import FoodCatalogItem, NutritionCatalogVersion
from app.planning.models import ControlledRecipe, ControlledRecipeIngredient


class ControlledRecipeImportError(ValueError):
    """A local recipe seed cannot safely become a user-visible candidate."""


class SeedPortion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    description: str = Field(min_length=1, max_length=120)
    grams: Decimal = Field(gt=0, le=Decimal("2000"))


class SeedIngredient(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    catalog_item_stable_id: str = Field(pattern=r"^fdc:\d+$")
    catalog_version: str = Field(min_length=1, max_length=80)
    grams: Decimal = Field(gt=0, le=Decimal("2000"))
    portion_description: str = Field(min_length=1, max_length=120)


class SeedRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    stable_id: str = Field(min_length=1, max_length=120)
    display_name: str = Field(min_length=1, max_length=200)
    meal_slots: tuple[str, ...] = Field(min_length=1, max_length=1)
    portion: SeedPortion
    method_tags: tuple[str, ...] = Field(min_length=1)
    flavour_tags: tuple[str, ...] = Field(min_length=1)
    source_kind: str
    source_reference: str = Field(min_length=1)
    license_name: str
    audit_status: str
    audited_at: datetime
    audited_by_role: str
    audit_version: str = Field(min_length=1, max_length=80)
    ingredients: tuple[SeedIngredient, ...] = Field(min_length=1)

    @field_validator("meal_slots")
    @classmethod
    def requires_one_stable_slot(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value[0] not in {"breakfast", "lunch", "dinner"}:
            raise ValueError("controlled recipe has an unsupported meal slot")
        return value


class ControlledRecipeManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str
    recipe_version: str = Field(min_length=1, max_length=80)
    catalog_version: str = Field(min_length=1, max_length=80)
    recipes: tuple[SeedRecipe, ...] = Field(min_length=3)

    @field_validator("schema_version")
    @classmethod
    def requires_known_schema(cls, value: str) -> str:
        if value != "controlled-recipes.v1":
            raise ValueError("controlled recipe seed schema is not supported")
        return value


def load_manifest(path: Path) -> ControlledRecipeManifest:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TypeError("seed is not an object")
        manifest = ControlledRecipeManifest.model_validate(payload)
    except (OSError, TypeError, json.JSONDecodeError, ValidationError) as error:
        raise ControlledRecipeImportError("controlled recipe seed is invalid") from error
    if {recipe.meal_slots[0] for recipe in manifest.recipes} != {"breakfast", "lunch", "dinner"}:
        raise ControlledRecipeImportError("controlled recipe seed must contain exactly three slots")
    if any(
        recipe.source_kind != "project_authored"
        or recipe.license_name != "LicenseRef-Project-Authored-v1"
        or recipe.audit_status != "approved"
        or recipe.audited_by_role != "nutrition_catalog_reviewer"
        or any(item.catalog_version != manifest.catalog_version for item in recipe.ingredients)
        for recipe in manifest.recipes
    ):
        raise ControlledRecipeImportError("controlled recipe seed violates the audit contract")
    return manifest


def apply_manifest(manifest: ControlledRecipeManifest, database_url: str) -> bool:
    """Write an immutable version once, after every ingredient is proved qualified."""

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with Session(engine) as session:
            catalog = session.scalar(
                select(NutritionCatalogVersion).where(NutritionCatalogVersion.version == manifest.catalog_version)
            )
            if catalog is None:
                raise ControlledRecipeImportError("controlled recipe catalog version is unavailable")
            existing = session.scalar(
                select(ControlledRecipe.id).where(ControlledRecipe.recipe_version == manifest.recipe_version)
            )
            if existing is not None:
                return False
            for recipe in manifest.recipes:
                model = ControlledRecipe(
                    stable_id=recipe.stable_id,
                    display_name=recipe.display_name,
                    recipe_version=manifest.recipe_version,
                    catalog_version_id=catalog.id,
                    catalog_version=manifest.catalog_version,
                    meal_slot=recipe.meal_slots[0],
                    portion_description=recipe.portion.description,
                    portion_grams=recipe.portion.grams,
                    method_tags="|".join(recipe.method_tags),
                    flavour_tags="|".join(recipe.flavour_tags),
                    source_kind=recipe.source_kind,
                    source_reference=recipe.source_reference,
                    license_name=recipe.license_name,
                    audit_status=recipe.audit_status,
                    audited_at=recipe.audited_at,
                    audited_by_role=recipe.audited_by_role,
                    audit_version=recipe.audit_version,
                    is_active=True,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
                for position, ingredient in enumerate(recipe.ingredients):
                    food = session.scalar(
                        select(FoodCatalogItem).where(
                            FoodCatalogItem.catalog_version_id == catalog.id,
                            FoodCatalogItem.stable_id == ingredient.catalog_item_stable_id,
                            FoodCatalogItem.is_qualified.is_(True),
                        )
                    )
                    if food is None:
                        raise ControlledRecipeImportError("controlled recipe ingredient is not qualified")
                    model.ingredients.append(
                        ControlledRecipeIngredient(
                            food_catalog_item_id=food.id,
                            catalog_version=ingredient.catalog_version,
                            position=position,
                            grams=ingredient.grams,
                            portion_description=ingredient.portion_description,
                        )
                    )
                session.add(model)
            session.commit()
            return True
    except Exception:
        session.rollback()
        raise
    finally:
        engine.dispose()


def _database_url(value: str | None) -> str:
    return value or validate_test_database_configuration(Settings(_env_file=None))  # type: ignore[call-arg]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true")
    action.add_argument("--apply", action="store_true")
    parser.add_argument("path", type=Path)
    parser.add_argument("--database-url")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        manifest = load_manifest(arguments.path)
        if arguments.check:
            print(f"valid controlled recipes {manifest.recipe_version}")
            return 0
        changed = apply_manifest(manifest, _database_url(arguments.database_url))
        print("controlled recipes applied" if changed else "controlled recipes already applied")
        return 0
    except ControlledRecipeImportError:
        print("controlled recipe import failed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
