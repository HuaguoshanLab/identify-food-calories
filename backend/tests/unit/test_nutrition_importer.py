"""Contracts for the offline, versioned USDA catalog importer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.nutrition.importer import (
    CatalogImportError,
    CatalogImportService,
    CatalogManifest,
    ImportedCatalogVersion,
    load_manifest,
)


SEED_PATH = Path("app/nutrition/data/fdc-seed-v1.json")


def test_seed_manifest_is_a_qualified_offline_usda_catalog() -> None:
    manifest = load_manifest(SEED_PATH)

    assert manifest.catalog_key == "usda-fdc"
    assert 24 <= len(manifest.foods) <= 30
    assert manifest.content_hash
    rice = next(food for food in manifest.foods if food.stable_id == "fdc:169756")
    assert rice.is_qualified is True
    assert rice.prepared_state == "cooked"
    assert rice.nutrients_per_100g.energy_kcal is not None
    assert rice.source_url.endswith("/169756/nutrients")


def test_manifest_rejects_a_tampered_content_hash(tmp_path: Path) -> None:
    payload = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    payload["foods"][0]["canonical_name"] = "tampered food"
    tampered = tmp_path / "tampered.json"
    tampered.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CatalogImportError, match="content hash"):
        load_manifest(tampered)


class FakeCatalogImportRepository:
    def __init__(self) -> None:
        self.versions: dict[tuple[str, str], ImportedCatalogVersion] = {}
        self.added: list[CatalogManifest] = []

    def get_imported_version(
        self, *, catalog_key: str, version: str
    ) -> ImportedCatalogVersion | None:
        return self.versions.get((catalog_key, version))

    def add_manifest(self, manifest: CatalogManifest) -> None:
        self.added.append(manifest)
        self.versions[(manifest.catalog_key, manifest.version)] = ImportedCatalogVersion(
            version=manifest.version,
            content_hash=manifest.content_hash,
        )


def test_apply_is_idempotent_and_rejects_existing_version_hash_conflicts() -> None:
    manifest = load_manifest(SEED_PATH)
    repository = FakeCatalogImportRepository()
    commits: list[bool] = []
    service = CatalogImportService(
        repository=repository,
        commit=lambda: commits.append(True),
        rollback=lambda: None,
    )

    assert service.apply(manifest) is True
    assert service.apply(manifest) is False
    assert len(repository.added) == 1
    assert commits == [True]

    conflicting = manifest.model_copy(update={"content_hash": "0" * 64})
    with pytest.raises(CatalogImportError, match="different content hash"):
        service.apply(conflicting)
