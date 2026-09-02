"""Apply the bounded food and controlled-recipe seeds to the guarded local database.

This is deliberately separate from migrations: schema changes must remain Alembic-owned,
while catalog and recipe truth is an explicit, idempotent operational action.
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import ConfigurationError, Settings, runtime_database_url
from app.nutrition.importer import apply_manifest as apply_catalog_manifest
from app.nutrition.importer import load_manifest as load_catalog_manifest
from app.planning.importer import apply_manifest as apply_recipe_manifest
from app.planning.importer import load_manifest as load_recipe_manifest


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def guarded_local_database_url() -> str:
    """Allow seed writes only to the conventional local development database."""

    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    if settings.app_env != "local":
        raise ConfigurationError("local planning bootstrap requires APP_ENV=local")
    database_url = runtime_database_url(settings)
    parsed = make_url(database_url)
    if parsed.host not in {"localhost", "127.0.0.1", "::1"}:
        raise ConfigurationError("local planning bootstrap requires a loopback PostgreSQL host")
    if parsed.database != "food_agent_dev":
        raise ConfigurationError("local planning bootstrap requires the food_agent_dev database")
    return database_url


def main() -> int:
    try:
        database_url = guarded_local_database_url()
        catalog_paths = (
            "app/nutrition/data/fdc-seed-v1.json",
            "app/nutrition/data/fdc-seed-v1-rice-fist-v1.json",
            "app/nutrition/data/chili-fried-pork-reference-v2.json",
        )
        for relative_path in catalog_paths:
            changed = apply_catalog_manifest(load_catalog_manifest(BACKEND_ROOT / relative_path), database_url)
            print(f"{relative_path}: {'applied' if changed else 'already applied'}")
        for recipe_path in (
            "app/planning/data/controlled-recipes.v1.json",
            "app/planning/data/controlled-recipes.v2.json",
        ):
            changed = apply_recipe_manifest(load_recipe_manifest(BACKEND_ROOT / recipe_path), database_url)
            print(f"{recipe_path}: {'applied' if changed else 'already applied'}")
        return 0
    except (ConfigurationError, SQLAlchemyError, ValueError):
        print("local planning bootstrap failed", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
