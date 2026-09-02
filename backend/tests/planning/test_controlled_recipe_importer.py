"""Version-selection contracts for auditable controlled-recipe seed data."""

from __future__ import annotations

from pathlib import Path

from app.planning.importer import load_manifest
from app.planning.schemas import CONTROLLED_RECIPE_VERSION


DATA_ROOT = Path("app/planning/data")


def test_v2_manifest_is_the_explicitly_selected_recipe_version() -> None:
    manifest = load_manifest(DATA_ROOT / "controlled-recipes.v2.json")

    assert manifest.recipe_version == CONTROLLED_RECIPE_VERSION
    assert {recipe.meal_slots[0] for recipe in manifest.recipes} == {
        "breakfast", "lunch", "dinner"
    }
    assert sum(recipe.meal_slots == ("lunch",) for recipe in manifest.recipes) >= 2
    assert sum(recipe.meal_slots == ("dinner",) for recipe in manifest.recipes) >= 2


def test_v1_manifest_remains_a_distinct_immutable_history_version() -> None:
    historical = load_manifest(DATA_ROOT / "controlled-recipes.v1.json")

    assert historical.recipe_version == "controlled-recipes.v1"
    assert historical.recipe_version != CONTROLLED_RECIPE_VERSION
