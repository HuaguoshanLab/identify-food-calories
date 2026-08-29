"""Repository capabilities used by deterministic nutrition services."""

from __future__ import annotations

import uuid
from typing import Protocol

from app.nutrition.importer import CatalogManifest, ImportedCatalogVersion
from app.nutrition.schemas import QualifiedFood


class NutritionRepository(Protocol):
    """Only exposes qualified, versioned catalog records to the service."""

    def search_qualified_foods(self, *, normalized_query: str, limit: int) -> list[QualifiedFood]: ...

    def get_qualified_food(
        self, *, food_id: uuid.UUID, catalog_version: str
    ) -> QualifiedFood | None: ...


class NutritionCatalogImportRepository(Protocol):
    """Persistence operations for immutable, offline catalog imports."""

    def get_imported_version(
        self, *, catalog_key: str, version: str
    ) -> ImportedCatalogVersion | None: ...

    def add_manifest(self, manifest: CatalogManifest) -> None: ...
