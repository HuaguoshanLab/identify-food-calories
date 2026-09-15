"""Pure deterministic nutrition tools over a repository port."""

from __future__ import annotations

import asyncio
import time
from decimal import Decimal

from app.core.tracing import DisabledTracingRuntime, TracingRuntime
from app.nutrition.ports import HybridFoodSearchRepository, NutritionRepository
from app.nutrition.search import fuse_food_search_evidence
from app.nutrition.schemas import (
    MAX_CATALOG_CANDIDATES,
    FoodRelation,
    FoodSearchCandidate,
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
from app.providers.embedding.dto import EmbeddingRequest
from app.providers.embedding.ports import EmbeddingProvider
from app.providers.reasoning.dto import ProviderCallError, ProviderFailureKind


HUNDRED_GRAMS = Decimal("100")
MAX_ITEM_GRAMS = Decimal("2000")
MAX_ENERGY_KCAL_PER_100G = Decimal("900")
MAX_MACRO_G_PER_100G = Decimal("100")
TOTAL_TOLERANCE = Decimal("0.000001")
SEMANTIC_RECALL_LIMIT = 12
EMBEDDING_TIMEOUT_SECONDS = 2.0


def normalize_food_name(value: str) -> str:
    """Normalize only case and insignificant whitespace, never spelling or semantics."""

    return " ".join(value.casefold().split())


class NutritionService:
    """Deterministic catalog search, calculation and validation application service."""

    def __init__(
        self,
        *,
        repository: NutritionRepository,
        search_repository: HybridFoodSearchRepository | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        tracing: TracingRuntime | None = None,
    ) -> None:
        self._repository = repository
        self._search_repository = search_repository
        self._embedding_provider = embedding_provider
        self._tracing = tracing or DisabledTracingRuntime()

    async def search_food_catalog(self, request: FoodSearchInput) -> FoodSearchResult:
        """Resolve one exact authority or return ASK-only hybrid candidates.

        Query text and its vector are deliberately local variables: neither the
        repository, provider Fake trace nor Phoenix receives a reusable payload.
        """

        normalized_query = normalize_food_name(request.query)
        if self._search_repository is None or self._embedding_provider is None:
            return self._legacy_search(request, normalized_query)

        exact_matches = self._search_repository.find_current_qualified_exact(
            normalized_query=normalized_query
        )
        if len(exact_matches) == 1:
            return self._trace_result(
                self._pass_exact(request, exact_matches[0]),
                channel="exact",
                fallback_code="none",
                started_at=time.monotonic(),
            )
        if len(exact_matches) > 1:
            return self._trace_result(
                FoodSearchResult(
                    action=NutritionAction.ASK, query=request.query,
                    candidates=tuple(self._legacy_candidate(food) for food in exact_matches[:MAX_CATALOG_CANDIDATES]),
                    safe_message="存在多个合格的同名条目，请确认使用的来源。",
                ),
                channel="exact", fallback_code="none", started_at=time.monotonic(),
            )

        started_at = time.monotonic()
        fallback_code = "none"
        text_evidence = self._search_repository.find_text_candidates(
            normalized_query=normalized_query, limit=SEMANTIC_RECALL_LIMIT
        )
        vector_evidence = []
        try:
            embedding = await asyncio.wait_for(
                self._embedding_provider.embed(
                    EmbeddingRequest(
                        names=(normalized_query,),
                        text_type="query",
                        model_alias="hybrid-food-query-v1",
                    )
                ),
                timeout=EMBEDDING_TIMEOUT_SECONDS,
            )
            query_vector = tuple(embedding.vectors[0].values)
            vector_evidence = self._search_repository.find_vector_candidates(
                query_vector=query_vector, limit=SEMANTIC_RECALL_LIMIT
            )
        except asyncio.TimeoutError:
            fallback_code = "embedding_timeout"
        except ProviderCallError as error:
            # An un-scripted Fake is the local/test-safe "semantic unavailable"
            # sentinel.  Do not broaden this exception: a real provider rejection
            # must remain fail-closed rather than being silently hidden as search.
            if error.code == "FAKE_UNSCRIPTED_CALL":
                fallback_code = "semantic_unavailable"
            elif error.kind not in {
                ProviderFailureKind.TRANSIENT,
                ProviderFailureKind.OUTCOME_UNKNOWN,
            }:
                raise
            else:
                fallback_code = "embedding_unavailable"
        except (ConnectionError, ValueError):
            fallback_code = "semantic_unavailable"

        fused = fuse_food_search_evidence([*text_evidence, *vector_evidence])
        rematerialized = tuple(
            self._current_candidate(candidate, food)
            for candidate in fused.candidates
            if (
                food := self._search_repository.get_current_qualified_food(
                    food_id=candidate.food_id,
                    catalog_version=candidate.catalog_version,
                )
            )
            is not None
        )
        result = FoodSearchResult(
            action=NutritionAction.ASK,
            query=request.query,
            candidates=rematerialized,
            safe_message="请从候选食物中选择最符合的一项。"
            if rematerialized
            else "目录中没有可直接计算的匹配项，请更换名称或排除该项。",
        )
        return self._trace_result(
            result,
            channel="text" if fallback_code != "none" else "text+vector",
            fallback_code=fallback_code,
            started_at=started_at,
        )

    def _legacy_search(self, request: FoodSearchInput, normalized_query: str) -> FoodSearchResult:
        """Keep un-wired callers fail-safe until the lifespan factory injects hybrid ports."""

        candidates = self._repository.search_qualified_foods(
            normalized_query=normalized_query, limit=MAX_CATALOG_CANDIDATES
        )[:MAX_CATALOG_CANDIDATES]
        exact_matches = [
            food for food in candidates
            if normalized_query in {normalize_food_name(alias) for alias in food.aliases}
        ]
        if len(exact_matches) == 1:
            return self._pass_exact(request, exact_matches[0])
        if candidates:
            return FoodSearchResult(
                action=NutritionAction.ASK,
                query=request.query,
                candidates=tuple(self._legacy_candidate(food) for food in candidates),
                safe_message="请从候选食物中选择最符合的一项。",
            )
        return FoodSearchResult(
            action=NutritionAction.ASK,
            query=request.query,
            safe_message="目录中没有可直接计算的匹配项，请更换名称或排除该项。",
        )

    @staticmethod
    def _pass_exact(request: FoodSearchInput, food: QualifiedFood) -> FoodSearchResult:
        return FoodSearchResult(
            action=NutritionAction.PASS,
            query=request.query,
            selected_food=food,
            safe_message="已匹配到受控营养目录条目。",
        )

    @staticmethod
    def _current_candidate(
        candidate: FoodSearchCandidate, food: QualifiedFood
    ) -> FoodSearchCandidate:
        """Re-read authority without discarding controlled relation evidence."""

        return FoodSearchCandidate(
            food_id=food.id,
            catalog_version=food.catalog_version,
            canonical_name=food.canonical_name,
            relation=candidate.relation,
            prepared_state=food.prepared_state,
            portion_hints=tuple(
                portion.description for portion in food.portions if portion.audited
            )[:3],
            source_name=food.source_name,
        )

    @staticmethod
    def _legacy_candidate(food: QualifiedFood) -> FoodSearchCandidate:
        """Legacy lookup has no governed relation evidence, so remain conservative."""

        return FoodSearchCandidate(
            food_id=food.id,
            catalog_version=food.catalog_version,
            canonical_name=food.canonical_name,
            relation=FoodRelation.SAME_CLASS,
            prepared_state=food.prepared_state,
            portion_hints=tuple(
                portion.description for portion in food.portions if portion.audited
            )[:3],
            source_name=food.source_name,
        )

    def _trace_result(
        self,
        result: FoodSearchResult,
        *,
        channel: str,
        fallback_code: str,
        started_at: float,
    ) -> FoodSearchResult:
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        with self._tracing.span(
            "nutrition.hybrid_search",
            {
                "retrieval.version": "hybrid-food-retrieval-v1",
                "match.channel": channel,
                "fallback.code": fallback_code,
                "latency.bucket": "under_2s" if elapsed_ms < 2000 else "over_2s",
                "index.health": "degraded" if fallback_code != "none" else "ready",
                "index.version": "active",
                "status.code": result.action.value,
                "tool.name": "search_food_catalog",
                "tool.version": "nutrition-tools-v1",
            },
        ) as trace_span:
            if trace_span is not None:
                trace_span.update(
                    input={"query": result.query},
                    output={
                        "action": result.action.value,
                        "selected_food": (
                            result.selected_food.canonical_name if result.selected_food else None
                        ),
                        "candidates": [candidate.canonical_name for candidate in result.candidates],
                    },
                )
            return result

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
