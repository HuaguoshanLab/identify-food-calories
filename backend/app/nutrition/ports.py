"""Repository capabilities used by deterministic nutrition services."""

from __future__ import annotations

import uuid
from typing import Protocol

from app.nutrition.importer import CatalogManifest, ImportedCatalogVersion
from app.nutrition.schemas import FoodSearchEvidence, QualifiedFood


class NutritionRepository(Protocol):
    """Only exposes qualified, versioned catalog records to the service."""

    def search_qualified_foods(self, *, normalized_query: str, limit: int) -> list[QualifiedFood]: ...

    def get_qualified_food(
        self, *, food_id: uuid.UUID, catalog_version: str
    ) -> QualifiedFood | None: ...


class HybridFoodSearchRepository(Protocol):
    """Authoritative retrieval capabilities used by the nutrition application service."""

    def find_current_qualified_exact(
        self, *, normalized_query: str
    ) -> list[QualifiedFood]: ...

    def find_text_candidates(
        self, *, normalized_query: str, limit: int
    ) -> list[FoodSearchEvidence]: ...

    def find_vector_candidates(
        self, *, query_vector: tuple[float, ...], limit: int
    ) -> list[FoodSearchEvidence]: ...

    def get_current_qualified_food(
        self, *, food_id: uuid.UUID, catalog_version: str
    ) -> QualifiedFood | None: ...


class NutritionCatalogImportRepository(Protocol):
    """Persistence operations for immutable, offline catalog imports."""

    def get_imported_version(
        self, *, catalog_key: str, version: str
    ) -> ImportedCatalogVersion | None: ...

    def add_manifest(self, manifest: CatalogManifest) -> None: ...
