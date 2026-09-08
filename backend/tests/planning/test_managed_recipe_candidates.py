"""Domain contracts for administrator-managed prepared-dish candidates."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.planning.schemas import (
    ManagedRecipeCandidate,
    ManagedRecipeCandidateStatus,
    MealCompositionResult,
    MealSlot,
    PlanValidationAction,
)


def candidate(*, slot: MealSlot = MealSlot.BREAKFAST, **changes: object) -> ManagedRecipeCandidate:
    values: dict[str, object] = {
        "id": uuid.uuid4(),
        "nutrition_item_id": uuid.uuid4(),
        "catalog_version": "fdc-foundation-2026-04",
        "display_name": "番茄炒蛋",
        "meal_slot": slot,
        "portion_grams": Decimal("180"),
        "portion_description": "一盘",
        "method_tags": ("炒",),
        "flavour_tags": ("家常",),
        "status": ManagedRecipeCandidateStatus.ENABLED,
        "revision": 1,
    }
    values.update(changes)
    return ManagedRecipeCandidate.model_validate(values)


def test_managed_candidate_only_carries_catalog_reference_and_display_metadata() -> None:
    item = candidate()

    assert item.nutrition_item_id
    assert item.meal_slot is MealSlot.BREAKFAST
    assert "energy_kcal" not in item.model_dump()
    with pytest.raises(ValidationError):
        ManagedRecipeCandidate.model_validate({**item.model_dump(), "stored_total": {"energy_kcal": "1"}})


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "draft"},
        {"portion_grams": "0"},
        {"portion_description": ""},
        {"method_tags": ()},
        {"flavour_tags": ()},
        {"revision": 0},
        {"catalog_version": ""},
    ],
)
def test_managed_candidate_rejects_unusable_lifecycle_or_content(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        candidate(**changes)


def test_main_meals_are_required_but_snack_is_optional() -> None:
    with pytest.raises(ValidationError):
        MealCompositionResult(
            action=PlanValidationAction.PASS,
            meals=(),
            safe_message="test",
        )
    assert MealSlot.SNACK.value == "snack"
