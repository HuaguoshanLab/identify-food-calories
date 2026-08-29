"""Offline, hash-verified importer for the bounded USDA FDC seed catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings, validate_test_database_configuration
from app.nutrition.schemas import ControlledPortion, NutritionValues


class CatalogImportError(ValueError):
    """Raised when a seed cannot safely become catalog truth."""


class SourceProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset: str = Field(pattern=r"^[a-z0-9-]+$")
    release: str = Field(min_length=1, max_length=80)
    source_name: str = Field(min_length=1, max_length=120)
    source_url: str = Field(min_length=1, max_length=500)
    license_name: str = Field(min_length=1, max_length=120)

    @model_validator(mode="after")
    def requires_usda_cc0(self) -> "SourceProvenance":
        if self.source_name != "USDA FoodData Central":
            raise ValueError("seed source must be USDA FoodData Central")
        if self.license_name != "CC0 1.0":
            raise ValueError("seed source must be licensed CC0 1.0")
        if not self.source_url.startswith("https://fdc.nal.usda.gov/"):
            raise ValueError("seed source URL must be the USDA FDC site")
        return self


class SeedFood(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    stable_id: str = Field(pattern=r"^fdc:\d+$")
    source_url: str = Field(min_length=1, max_length=500)
    canonical_name: str = Field(min_length=1, max_length=200)
    prepared_state: str = Field(min_length=1, max_length=120)
    is_qualified: bool
    nutrients_per_100g: NutritionValues
    aliases: tuple[str, ...] = Field(min_length=1)
    portions: tuple[ControlledPortion, ...] = ()

    @field_validator("aliases")
    @classmethod
    def aliases_are_controlled(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(alias.casefold().strip() for alias in value)) != len(value):
            raise ValueError("food aliases must be unique after normalization")
        return value

    @model_validator(mode="after")
    def qualified_records_have_complete_truth(self) -> "SeedFood":
        if not self.is_qualified:
            raise ValueError("the bounded seed must not contain unqualified fallback foods")
        if any(value is None for value in self.nutrients_per_100g.model_dump().values()):
            raise ValueError("null nutrient values must not become zero")
        fdc_id = self.stable_id.removeprefix("fdc:")
        if self.source_url != f"https://fdc.nal.usda.gov/food-details/{fdc_id}/nutrients":
            raise ValueError("food source URL must exactly match its FDC id")
        return self


class CatalogManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "fdc-seed-v1"
    catalog_key: str = Field(pattern=r"^[a-z0-9-]+$")
    catalog_display_name: str = Field(min_length=1, max_length=160)
    version: str = Field(min_length=1, max_length=80)
    released_at: datetime
    provenance: SourceProvenance
    foods: tuple[SeedFood, ...]
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def enforces_bounded_fdc_seed(self) -> "CatalogManifest":
        if self.catalog_key != "usda-fdc":
            raise ValueError("only the approved usda-fdc catalog key is allowed")
        if not 24 <= len(self.foods) <= 30:
            raise ValueError("the bounded seed must contain 24 to 30 records")
        if len({food.stable_id for food in self.foods}) != len(self.foods):
            raise ValueError("FDC ids must be unique")
        return self


class ImportedCatalogVersion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: str
    content_hash: str


def manifest_content_hash(payload: dict[str, Any]) -> str:
    """Hash canonical payload excluding its self-referential hash field."""

    canonical_payload = {key: value for key, value in payload.items() if key != "content_hash"}
    canonical = json.dumps(canonical_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_manifest(path: Path) -> CatalogManifest:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CatalogImportError("seed manifest must be valid local JSON") from error
    if not isinstance(payload, dict):
        raise CatalogImportError("seed manifest must be a JSON object")
    declared_hash = payload.get("content_hash")
    if not isinstance(declared_hash, str) or manifest_content_hash(payload) != declared_hash:
        raise CatalogImportError("seed manifest content hash does not match")
    try:
        return CatalogManifest.model_validate(payload)
    except ValidationError as error:
        raise CatalogImportError("seed manifest violates the FDC catalog contract") from error


class CatalogImportService:
    """Service owns immutable version semantics; the repository only persists rows."""

    def __init__(
        self,
        *,
        repository: Any,
        commit: Callable[[], None],
        rollback: Callable[[], None],
    ) -> None:
        self._repository = repository
        self._commit = commit
        self._rollback = rollback

    def apply(self, manifest: CatalogManifest) -> bool:
        existing = self._repository.get_imported_version(
            catalog_key=manifest.catalog_key, version=manifest.version
        )
        if existing is not None:
            if existing.content_hash != manifest.content_hash:
                raise CatalogImportError("catalog version already exists with a different content hash")
            return False
        try:
            self._repository.add_manifest(manifest)
            self._commit()
        except Exception:
            self._rollback()
            raise
        return True


def _database_url(value: str | None) -> str:
    if value:
        return value
    # CLI defaults are deliberately test-only. Production deployment passes its
    # explicitly reviewed catalog target; no local/SQLite fallback is permitted.
    return validate_test_database_configuration(Settings(_env_file=None))  # type: ignore[call-arg]


def apply_manifest(manifest: CatalogManifest, database_url: str) -> bool:
    from app.nutrition.repository import SqlAlchemyNutritionCatalogImportRepository

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with Session(engine) as session:
            service = CatalogImportService(
                repository=SqlAlchemyNutritionCatalogImportRepository(session),
                commit=session.commit,
                rollback=session.rollback,
            )
            return service.apply(manifest)
    finally:
        engine.dispose()


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
            print(f"valid FDC catalog {manifest.version} {manifest.content_hash}")
            return 0
        changed = apply_manifest(manifest, _database_url(arguments.database_url))
        print("catalog applied" if changed else "catalog already applied")
        return 0
    except CatalogImportError as error:
        print(f"catalog import rejected: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
