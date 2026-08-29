"""Pure deterministic nutrition tools over a repository port."""

from __future__ import annotations

from decimal import Decimal

from app.nutrition.ports import NutritionRepository
from app.nutrition.schemas import (
    MAX_CATALOG_CANDIDATES,
    FoodSearchInput,
    FoodSearchResult,
    NutritionAction,
    NutritionCalculationInput,
    NutritionCalculationResult,
    NutritionValidationInput,
    NutritionValidationResult,
    NutritionValues,
    QualifiedFood,
)


HUNDRED_GRAMS = Decimal("100")
MAX_ITEM_GRAMS = Decimal("2000")
MAX_ENERGY_KCAL_PER_100G = Decimal("900")
MAX_MACRO_G_PER_100G = Decimal("100")
TOTAL_TOLERANCE = Decimal("0.000001")


def normalize_food_name(value: str) -> str:
    """Normalize only case and insignificant whitespace, never spelling or semantics."""

    return " ".join(value.casefold().split())


class NutritionService:
    """Deterministic catalog search, calculation and validation application service."""

    def __init__(self, *, repository: NutritionRepository) -> None:
        self._repository = repository

    def search_food_catalog(self, request: FoodSearchInput) -> FoodSearchResult:
        normalized_query = normalize_food_name(request.query)
        candidates = self._repository.search_qualified_foods(
            normalized_query=normalized_query,
            limit=MAX_CATALOG_CANDIDATES,
        )[:MAX_CATALOG_CANDIDATES]
        exact_matches = [
            food
            for food in candidates
            if normalized_query in {normalize_food_name(alias) for alias in food.aliases}
        ]
        if len(exact_matches) == 1:
            return FoodSearchResult(
                action=NutritionAction.PASS,
                query=request.query,
                selected_food=exact_matches[0],
                safe_message="已匹配到受控营养目录条目。",
            )
        if candidates:
            return FoodSearchResult(
                action=NutritionAction.ASK,
                query=request.query,
                candidates=tuple(candidates),
                safe_message="请从候选食物中选择最符合的一项。",
            )
        return FoodSearchResult(
            action=NutritionAction.ASK,
            query=request.query,
            safe_message="目录中没有可直接计算的匹配项，请更换名称或排除该项。",
        )

    def calculate_nutrition(
        self, request: NutritionCalculationInput
    ) -> NutritionCalculationResult:
        food = self._repository.get_qualified_food(
            food_id=request.food_id, catalog_version=request.catalog_version
        )
        if food is None:
            return NutritionCalculationResult(
                action=NutritionAction.BLOCK,
                safe_message="所选食物不属于当前可计算的营养目录版本。",
            )
        grams = request.grams
        if grams is None and request.portion_description is not None:
            portions = [
                portion
                for portion in food.portions
                if portion.audited
                and normalize_food_name(portion.description)
                == normalize_food_name(request.portion_description)
            ]
            if len(portions) == 1:
                grams = portions[0].grams
        if grams is None:
            return NutritionCalculationResult(
                action=NutritionAction.ASK,
                safe_message="请提供可审计的克数或选择受控常见份量。",
            )
        if grams <= 0:
            return NutritionCalculationResult(
                action=NutritionAction.ASK,
                safe_message="份量必须大于 0 克，请更正后继续。",
            )
        if grams > MAX_ITEM_GRAMS:
            return NutritionCalculationResult(
                action=NutritionAction.BLOCK,
                safe_message="单项份量超过安全计算上限，请拆分或更正输入。",
            )

        factor = grams / HUNDRED_GRAMS
        source = food.nutrients_per_100g
        return NutritionCalculationResult(
            action=NutritionAction.PASS,
            food=food,
            grams=grams,
            nutrients=NutritionValues(
                energy_kcal=source.energy_kcal * factor,
                protein_g=source.protein_g * factor,
                fat_g=source.fat_g * factor,
                carbohydrate_g=source.carbohydrate_g * factor,
            ),
            safe_message="营养值已按目录每 100 克基准确定性计算。",
        )

    def validate_nutrition_result(
        self, request: NutritionValidationInput
    ) -> NutritionValidationResult:
        calculation = request.calculation
        if calculation.action is not NutritionAction.PASS:
            return NutritionValidationResult(
                action=calculation.action,
                rule_id="calculation-action-propagation",
                safe_message="必须先处理计算阶段给出的确定性动作。",
                food_id=calculation.food.id if calculation.food is not None else None,
            )

        assert calculation.food is not None
        assert calculation.grams is not None
        assert calculation.nutrients is not None
        density = calculation.food.nutrients_per_100g
        if any(
            value < 0
            for value in (
                density.energy_kcal,
                density.protein_g,
                density.fat_g,
                density.carbohydrate_g,
            )
        ):
            return self._validation(
                NutritionAction.BLOCK,
                "non-negative-nutrients",
                "营养目录包含负值，不能生成结果。",
                calculation.food,
            )
        if (
            density.energy_kcal > MAX_ENERGY_KCAL_PER_100G
            or density.protein_g > MAX_MACRO_G_PER_100G
            or density.fat_g > MAX_MACRO_G_PER_100G
            or density.carbohydrate_g > MAX_MACRO_G_PER_100G
        ):
            return self._validation(
                NutritionAction.BLOCK,
                "density-upper-bound",
                "营养密度超出安全范围，不能生成结果。",
                calculation.food,
            )
        expected = self._recalculate(calculation.food, calculation.grams)
        if not self._same_values(expected, calculation.nutrients):
            return self._validation(
                NutritionAction.RECALCULATE,
                "item-total-recalculation",
                "项目营养值与目录重算结果不一致，需要重新核算。",
                calculation.food,
            )
        if request.reported_total is not None and not self._same_values(
            calculation.nutrients, request.reported_total
        ):
            return self._validation(
                NutritionAction.RECALCULATE,
                "reported-total-recalculation",
                "汇总值与已计入项目不一致，需要重新核算。",
                calculation.food,
            )

        atwater_energy = (
            density.protein_g * Decimal("4")
            + density.carbohydrate_g * Decimal("4")
            + density.fat_g * Decimal("9")
        )
        if abs(density.energy_kcal - atwater_energy) > Decimal("50"):
            return self._validation(
                NutritionAction.WARN,
                "atwater-energy-difference",
                "来源能量与常用宏量推导存在差异，结果仍保留来源值。",
                calculation.food,
            )
        return self._validation(
            NutritionAction.PASS,
            "nutrition-validation-pass",
            "营养结果通过确定性校验。",
            calculation.food,
        )

    @staticmethod
    def _recalculate(food: QualifiedFood, grams: Decimal) -> NutritionValues:
        factor = grams / HUNDRED_GRAMS
        source = food.nutrients_per_100g
        return NutritionValues(
            energy_kcal=source.energy_kcal * factor,
            protein_g=source.protein_g * factor,
            fat_g=source.fat_g * factor,
            carbohydrate_g=source.carbohydrate_g * factor,
        )

    @staticmethod
    def _same_values(left: NutritionValues, right: NutritionValues) -> bool:
        return all(
            abs(first - second) <= TOTAL_TOLERANCE
            for first, second in zip(
                (
                    left.energy_kcal,
                    left.protein_g,
                    left.fat_g,
                    left.carbohydrate_g,
                ),
                (
                    right.energy_kcal,
                    right.protein_g,
                    right.fat_g,
                    right.carbohydrate_g,
                ),
                strict=True,
            )
        )

    @staticmethod
    def _validation(
        action: NutritionAction, rule_id: str, safe_message: str, food: QualifiedFood
    ) -> NutritionValidationResult:
        return NutritionValidationResult(
            action=action,
            rule_id=rule_id,
            safe_message=safe_message,
            food_id=food.id,
        )
