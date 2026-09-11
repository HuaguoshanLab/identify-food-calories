"""Fake-repository contracts for deterministic nutrition tools."""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.nutrition.schemas import (
    ControlledPortion,
    FoodSearchInput,
    NutritionAction,
    NutritionCalculationInput,
    NutritionValidationInput,
    NutritionValues,
    QualifiedFood,
)
from app.nutrition.service import NutritionService


class FakeNutritionRepository:
    """No SQLAlchemy or network dependency; records are already qualified fixtures."""

    def __init__(self, foods: list[QualifiedFood]) -> None:
        self.foods = foods
        self.search_calls: list[tuple[str, int]] = []

    def search_qualified_foods(self, *, normalized_query: str, limit: int) -> list[QualifiedFood]:
        self.search_calls.append((normalized_query, limit))
        return self.foods

    def get_qualified_food(
        self, *, food_id: uuid.UUID, catalog_version: str
    ) -> QualifiedFood | None:
        return next(
            (
                food
                for food in self.foods
                if food.id == food_id and food.catalog_version == catalog_version
            ),
            None,
        )


def food(
    *,
    name: str = "熟米饭",
    aliases: tuple[str, ...] = ("米饭",),
    nutrients: NutritionValues | None = None,
    portions: tuple[ControlledPortion, ...] = (),
) -> QualifiedFood:
    return QualifiedFood(
        id=uuid.uuid4(),
        canonical_name=name,
        catalog_version="fdc-foundation-2026-04",
        prepared_state="cooked",
        source_name="USDA FoodData Central",
        source_url="https://fdc.nal.usda.gov/",
        license_name="CC0 1.0",
        aliases=aliases,
        portions=portions,
        nutrients_per_100g=nutrients
        or NutritionValues(
            energy_kcal=Decimal("130"),
            protein_g=Decimal("2.7"),
            fat_g=Decimal("0.3"),
            carbohydrate_g=Decimal("28"),
        ),
    )


def calculate(service: NutritionService, selected_food: QualifiedFood, grams: Decimal | None):
    return service.calculate_nutrition(
        NutritionCalculationInput(
            food_id=selected_food.id,
            catalog_version=selected_food.catalog_version,
            grams=grams,
        )
    )


def test_unique_controlled_alias_is_selected_after_safe_normalization() -> None:
    selected_food = food()
    repository = FakeNutritionRepository([selected_food])

    result = asyncio.run(
        NutritionService(repository=repository).search_food_catalog(
            FoodSearchInput(query="  米饭 ")
        )
    )

    assert result.action is NutritionAction.PASS
    assert result.selected_food == selected_food
    assert result.candidates == ()
    assert repository.search_calls == [("米饭", 3)]


def test_ambiguous_search_exposes_at_most_three_qualified_candidates() -> None:
    candidates = [food(name=f"候选{i}", aliases=(f"候选{i}",)) for i in range(4)]

    result = asyncio.run(
        NutritionService(repository=FakeNutritionRepository(candidates)).search_food_catalog(
            FoodSearchInput(query="米饭")
        )
    )

    assert result.action is NutritionAction.ASK
    assert result.selected_food is None
    assert tuple(item.canonical_name for item in result.candidates) == ("候选0", "候选1", "候选2")


def test_missing_or_unaudited_portion_never_becomes_an_invented_gram_amount() -> None:
    selected_food = food(
        portions=(
            ControlledPortion(
                description="一碗",
                grams=Decimal("200"),
                source_reference="unreviewed local note",
                version="draft-1",
                audited=False,
            ),
        )
    )
    service = NutritionService(repository=FakeNutritionRepository([selected_food]))

    missing = calculate(service, selected_food, None)
    unaudited = service.calculate_nutrition(
        NutritionCalculationInput(
            food_id=selected_food.id,
            catalog_version=selected_food.catalog_version,
            portion_description="一碗",
        )
    )

    assert missing.action is NutritionAction.ASK
    assert unaudited.action is NutritionAction.ASK
    assert missing.nutrients is None
    assert unaudited.grams is None


def test_null_source_nutrient_is_rejected_not_replaced_with_zero() -> None:
    with pytest.raises(ValidationError):
        NutritionValues.model_validate(
            {
                "energy_kcal": None,
                "protein_g": Decimal("2"),
                "fat_g": Decimal("1"),
                "carbohydrate_g": Decimal("3"),
            }
        )


def test_decimal_calculation_preserves_internal_precision() -> None:
    selected_food = food()
    result = calculate(
        NutritionService(repository=FakeNutritionRepository([selected_food])),
        selected_food,
        Decimal("125.5"),
    )

    assert result.action is NutritionAction.PASS
    assert result.grams == Decimal("125.5")
    assert result.nutrients == NutritionValues(
        energy_kcal=Decimal("163.15"),
        protein_g=Decimal("3.3885"),
        fat_g=Decimal("0.3765"),
        carbohydrate_g=Decimal("35.14"),
    )


@pytest.mark.parametrize(
    ("grams", "expected_action"),
    [
        (Decimal("0"), NutritionAction.ASK),
        (Decimal("2000.01"), NutritionAction.BLOCK),
    ],
)
def test_invalid_gram_bounds_have_deterministic_actions(
    grams: Decimal, expected_action: NutritionAction
) -> None:
    selected_food = food()
    result = calculate(
        NutritionService(repository=FakeNutritionRepository([selected_food])), selected_food, grams
    )

    assert result.action is expected_action
    assert result.nutrients is None


def test_validation_returns_recalculate_for_tampered_item_or_total() -> None:
    selected_food = food()
    service = NutritionService(repository=FakeNutritionRepository([selected_food]))
    complete = calculate(service, selected_food, Decimal("100"))
    tampered = complete.model_copy(
        update={
            "nutrients": NutritionValues(
                energy_kcal=Decimal("1"),
                protein_g=Decimal("1"),
                fat_g=Decimal("1"),
                carbohydrate_g=Decimal("1"),
            )
        }
    )

    item_result = service.validate_nutrition_result(NutritionValidationInput(calculation=tampered))
    total_result = service.validate_nutrition_result(
        NutritionValidationInput(
            calculation=complete,
            reported_total=NutritionValues(
                energy_kcal=Decimal("1"),
                protein_g=Decimal("1"),
                fat_g=Decimal("1"),
                carbohydrate_g=Decimal("1"),
            ),
        )
    )

    assert item_result.action is NutritionAction.RECALCULATE
    assert total_result.action is NutritionAction.RECALCULATE


def test_validation_returns_block_warn_and_pass_without_model_input() -> None:
    normal_food = food()
    warning_food = food(
        name="高能来源记录",
        aliases=("高能",),
        nutrients=NutritionValues(
            energy_kcal=Decimal("300"),
            protein_g=Decimal("1"),
            fat_g=Decimal("1"),
            carbohydrate_g=Decimal("1"),
        ),
    )
    blocked_food = food(
        name="异常密度记录",
        aliases=("异常",),
        nutrients=NutritionValues(
            energy_kcal=Decimal("901"),
            protein_g=Decimal("1"),
            fat_g=Decimal("1"),
            carbohydrate_g=Decimal("1"),
        ),
    )
    service = NutritionService(
        repository=FakeNutritionRepository([normal_food, warning_food, blocked_food])
    )

    pass_result = service.validate_nutrition_result(
        NutritionValidationInput(calculation=calculate(service, normal_food, Decimal("100")))
    )
    warning_result = service.validate_nutrition_result(
        NutritionValidationInput(calculation=calculate(service, warning_food, Decimal("100")))
    )
    block_result = service.validate_nutrition_result(
        NutritionValidationInput(calculation=calculate(service, blocked_food, Decimal("100")))
    )

    assert pass_result.action is NutritionAction.PASS
    assert warning_result.action is NutritionAction.WARN
    assert block_result.action is NutritionAction.BLOCK


def test_validation_propagates_ask_without_permitting_a_report() -> None:
    selected_food = food()
    service = NutritionService(repository=FakeNutritionRepository([selected_food]))

    result = service.validate_nutrition_result(
        NutritionValidationInput(calculation=calculate(service, selected_food, None))
    )

    assert result.action is NutritionAction.ASK
    assert result.rule_id == "calculation-action-propagation"
