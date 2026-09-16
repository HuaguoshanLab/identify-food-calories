"""Pure, deterministic target-policy.v1 and safe plan-validation entry points."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable, Iterator
from datetime import UTC, datetime
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP
from itertools import islice
from time import monotonic

from app.planning.bundles import BUNDLE_ROLES, BUNDLE_SLOTS, BundlePool
from app.planning.diagnostics import SearchDiagnostics, SlotDiagnostics, ScanStop
from app.planning.models import PlanningCompletionProjection, PlanningProfile
from app.planning.ports import (
    PlanningCompletionProjectionRepository,
    PlanningNutritionPort,
    PlanningProfileRepository,
    PlanningRepository,
)
from app.planning.schemas import (
    ACTIVITY_FACTORS,
    CompositionFailureReason,
    HEALTH_REFUSAL_MESSAGE,
    DailyTarget,
    MealCompositionResult,
    MealSlot,
    ManagedRecipeCandidate,
    REQUIRED_MEAL_SLOTS,
    FormulaVariant,
    PlanValidationAction,
    PlanValidationResult,
    PlannedMeal,
    PlanningNutritionValues,
    PlanningGoal,
    PlanningProfilePatch,
    PlanningProfileInput,
    PlanningProfileWrite,
    PreferenceReview,
    FORMULA_VERSION,
    CONTROLLED_RECIPE_VERSION,
    TARGET_POLICY_VERSION,
    TargetCalculationResult,
    TargetRange,
)
from app.nutrition.schemas import NutritionAction, NutritionCalculationInput, NutritionValues
from app.planning.selection import (
    PlanningSearchBudget,
    MealSelectionPolicy,
    SelectionCandidate,
    SELECTION_POLICY_VERSION,
    matches_exclusion,
    normalized_label,
    select_meals,
)


MIN_ADULT_AGE = 19
MAX_ADULT_AGE = 78
MIN_SAFE_ENERGY_KCAL = Decimal("1200")
TARGET_RANGE_MARGIN_KCAL = Decimal("100")
CARBOHYDRATE_AMDR = (Decimal("0.45"), Decimal("0.65"))
PROTEIN_AMDR = (Decimal("0.10"), Decimal("0.35"))
FAT_AMDR = (Decimal("0.20"), Decimal("0.35"))
SPEED_DELTAS: dict[str, Decimal] = {
    "maintain": Decimal("0"),
    "gradual_loss": Decimal("-250"),
    "gradual_gain": Decimal("200"),
}


def safe_planning_stream_stage(event_type: str) -> str | None:
    """Map only persisted planning lifecycle signals to browser-safe stage values.

    This accepts no graph state, provider DTO, report, or exception. The SSE boundary calls it
    only with the ledger event label, so adding a graph node cannot serialize planning internals.
    """

    return {
        "reading_context": "perception",
        "needs_input": "awaiting_input",
        "tool_calculation": "tool_calculation",
        "validation": "validation",
        "completed_validated": "completed",
        "retryable": "retryable",
        "terminal": "terminal",
    }.get(event_type)


class PlanningService:
    """Owns safety decisions so browsers, graphs, and models cannot calculate targets."""

    def __init__(
        self, *, repository: PlanningRepository, nutrition_port: PlanningNutritionPort,
        search_budget: PlanningSearchBudget | None = None,
        selection_policy: MealSelectionPolicy | None = None,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._repository = repository
        self._nutrition_port = nutrition_port
        self._search_budget = search_budget or PlanningSearchBudget()
        self._selection_policy = selection_policy or MealSelectionPolicy()
        self._clock = clock

    def calculate_daily_target(
        self, profile: PlanningProfileInput, preferences: PreferenceReview
    ) -> TargetCalculationResult:
        """Return a target only after explicit confirmation and every safety guard passes."""

        if not self._has_complete_inputs(profile, preferences):
            return TargetCalculationResult(
                action=PlanValidationAction.NEEDS_INPUT,
                safe_message="请补全并确认身体资料、目标和饮食偏好后继续。",
            )
        if self._is_health_scope_blocked(profile):
            return TargetCalculationResult(
                action=PlanValidationAction.BLOCK_HEALTH_SCOPE,
                safe_message=HEALTH_REFUSAL_MESSAGE,
            )

        assert profile.height_cm is not None
        assert profile.weight_kg is not None
        assert profile.age_years is not None
        assert profile.formula_variant is not None
        assert profile.activity_level is not None
        assert profile.goal_speed is not None
        energy = (
            self._mifflin_st_jeor(profile)
            * ACTIVITY_FACTORS[profile.activity_level]
            + SPEED_DELTAS[profile.goal_speed]
        )
        energy_range = TargetRange(
            lower=energy - TARGET_RANGE_MARGIN_KCAL,
            upper=energy + TARGET_RANGE_MARGIN_KCAL,
        )
        if energy < MIN_SAFE_ENERGY_KCAL or energy_range.lower < MIN_SAFE_ENERGY_KCAL:
            return TargetCalculationResult(
                action=PlanValidationAction.BLOCK_HEALTH_SCOPE,
                safe_message=HEALTH_REFUSAL_MESSAGE,
            )

        return TargetCalculationResult(
            action=PlanValidationAction.PASS,
            target=DailyTarget(
                energy_kcal=energy_range,
                carbohydrate_g=self._macro_range(energy_range, CARBOHYDRATE_AMDR, Decimal("4")),
                protein_g=self._macro_range(energy_range, PROTEIN_AMDR, Decimal("4")),
                fat_g=self._macro_range(energy_range, FAT_AMDR, Decimal("9")),
            ),
            safe_message="每日目标区间已按版本化普通成人政策确定性计算。",
        )

    def validate_plan(
        self,
        *,
        target: DailyTarget,
        meals: tuple[PlannedMeal, ...],
        matched_exclusions: tuple[str, ...] = (),
        allow_target_relaxation: bool = False,
    ) -> PlanValidationResult:
        """Recompute the three-meal totals before any safe routing decision.

        The graph can ask for a validation result, but it cannot claim that a recipe
        combination is safe.  Keeping the aggregation here means a model, adapter,
        or client cannot turn a per-meal value into an unchecked daily plan.
        """

        if target.energy_kcal.lower < MIN_SAFE_ENERGY_KCAL:
            return PlanValidationResult(
                action=PlanValidationAction.BLOCK_HEALTH_SCOPE,
                rule_id="minimum-energy-floor",
                safe_message=HEALTH_REFUSAL_MESSAGE,
            )
        if not set(REQUIRED_MEAL_SLOTS).issubset({meal.slot for meal in meals}) or len({meal.slot for meal in meals}) != len(meals):
            return PlanValidationResult(
                action=PlanValidationAction.REPLAN,
                rule_id="incomplete-meal-slots",
                safe_message="餐单必须包含不重复的早餐、午餐和晚餐后才能校验。",
            )
        sources = [identity for meal in meals for identity in meal.source_recipe_ids]
        if len(set(sources)) != len(sources):
            return PlanValidationResult(
                action=PlanValidationAction.REPLAN,
                rule_id="duplicate-controlled-recipe",
                safe_message="同一受控菜谱不能在一天内重复使用。",
            )
        displayed_exclusions = tuple(
            summary
            for meal in meals
            for summary in meal.matched_exclusion_summaries
        )
        matched_exclusions = (*matched_exclusions, *displayed_exclusions)
        if matched_exclusions:
            return PlanValidationResult(
                action=PlanValidationAction.REPLAN,
                rule_id="confirmed-exclusion",
                safe_message="受控餐单包含已确认的排除项，不能放宽该约束。",
            )

        totals = self._daily_totals(meals)
        if totals.energy_kcal < MIN_SAFE_ENERGY_KCAL:
            return PlanValidationResult(
                action=PlanValidationAction.REPLAN,
                rule_id="minimum-plan-energy-floor",
                safe_message="当前三餐能量低于安全下限，不能通过放宽目标接受该餐单。",
            )

        # A range miss must never conceal a hard macro-ratio failure when relaxation is enabled.
        failed_metric = self._first_failed_macro_ratio(totals)
        if failed_metric is None:
            failed_metric = self._first_failed_target_metric(target=target, totals=totals)
        if failed_metric is None:
            return PlanValidationResult(
                action=PlanValidationAction.PASS,
                rule_id="planning-validation-pass",
                safe_message="餐单通过确定性总量、宏量比例、重复度和约束校验。",
            )
        if not failed_metric.endswith("-ratio"):
            # Every target dimension must pass the cap, not only the first miss.
            for metric in ("energy_kcal", "protein_g", "fat_g", "carbohydrate_g"):
                bounds = getattr(target, metric)
                value = getattr(totals, metric)
                edge = bounds.lower if value < bounds.lower else bounds.upper
                deviation = max(bounds.lower - value, value - bounds.upper, Decimal(0))
                if deviation > edge * self._selection_policy.max_target_deviation:
                    return PlanValidationResult(
                        action=PlanValidationAction.REPLAN,
                        rule_id=f"{metric}-deviation-limit",
                        safe_message="当前可用餐单与营养目标差距过大，不能自动放宽。请更换菜品或联系管理员补充合适菜谱。",
                    )
        if allow_target_relaxation and not failed_metric.endswith("-ratio"):
            return PlanValidationResult(
                action=PlanValidationAction.RELAX,
                rule_id=f"{failed_metric}-target-relaxation",
                relaxed_metric=failed_metric,
                safe_message="餐单部分指标未达到原目标，偏差在允许范围内；原目标和实际差距已保留，请查看后再使用。",
            )
        return PlanValidationResult(
            action=PlanValidationAction.REPLAN,
            rule_id=f"{failed_metric}-out-of-range",
            relaxation_available=not failed_metric.endswith("-ratio"),
            safe_message="三餐总量或宏量比例未满足当前目标，需要在受控候选中重新组合。",
        )

    def compose_daily_meals(
        self,
        *,
        user_id: uuid.UUID | None = None,
        catalog_version: str | None,
        preferences: PreferenceReview,
        recipe_version: str = CONTROLLED_RECIPE_VERSION,
        exclude_recipe_ids: tuple[uuid.UUID, ...] = (),
        required_food_id: uuid.UUID | None = None,
        required_catalog_version: str | None = None,
        required_slot: MealSlot | None = None,
        required_recipe_id: uuid.UUID | None = None,
        required_recipe_revision: int | None = None,
        target: DailyTarget | None = None,
        fixed_meals: tuple[PlannedMeal, ...] = (),
        feedback_intent: str | None = None,
    ) -> MealCompositionResult:
        """Record one count-only search summary, including failed searches."""
        diagnostics = SearchDiagnostics()
        started = self._clock()
        action = "error"
        reason: str | None = "internal_error"
        try:
            result = self._compose_daily_meals(
                diagnostics=diagnostics,
                user_id=user_id,
                catalog_version=catalog_version,
                preferences=preferences,
                recipe_version=recipe_version,
                exclude_recipe_ids=exclude_recipe_ids,
                required_food_id=required_food_id,
                required_catalog_version=required_catalog_version,
                required_slot=required_slot,
                required_recipe_id=required_recipe_id,
                required_recipe_revision=required_recipe_revision,
                target=target,
                fixed_meals=fixed_meals,
                feedback_intent=feedback_intent,
            )
            action = result.action.value
            reason = result.failure_reason.value if result.failure_reason is not None else None
            return result
        finally:
            diagnostics.elapsed_ms = max(0, int((self._clock() - started) * 1000))
            diagnostics.emit(action=action, reason=reason, policy=SELECTION_POLICY_VERSION)

    def _compose_daily_meals(
        self,
        *,
        user_id: uuid.UUID | None = None,
        catalog_version: str | None,
        preferences: PreferenceReview,
        recipe_version: str = CONTROLLED_RECIPE_VERSION,
        exclude_recipe_ids: tuple[uuid.UUID, ...] = (),
        required_food_id: uuid.UUID | None = None,
        required_catalog_version: str | None = None,
        required_slot: MealSlot | None = None,
        required_recipe_id: uuid.UUID | None = None,
        required_recipe_revision: int | None = None,
        target: DailyTarget | None = None,
        fixed_meals: tuple[PlannedMeal, ...] = (),
        feedback_intent: str | None = None,
        diagnostics: SearchDiagnostics,
    ) -> MealCompositionResult:
        """Select one fully qualified candidate per stable slot and recompute every ingredient."""

        if not preferences.confirmed:
            return MealCompositionResult(
                action=PlanValidationAction.NEEDS_INPUT,
                safe_message="请先确认本次要使用的忌口和口味偏好。",
            )
        if feedback_intent not in {None, "replace", "lighter"}:
            return MealCompositionResult(action=PlanValidationAction.NEEDS_INPUT, safe_message="请明确要调整的口味或菜品。")
        if fixed_meals and (
            required_slot is None
            or any(meal.slot is required_slot for meal in fixed_meals)
            or len({meal.slot for meal in fixed_meals}) != len(fixed_meals)
            or len({identity for meal in fixed_meals for identity in meal.source_recipe_ids}) != sum(len(meal.source_recipe_ids) for meal in fixed_meals)
        ):
            return MealCompositionResult(action=PlanValidationAction.NEEDS_INPUT, safe_message="原餐单或调整餐次无效，请重新打开计划。")
        if required_recipe_id is not None:
            if required_food_id is None or required_catalog_version is None or required_slot is None or required_recipe_revision is None:
                return MealCompositionResult(action=PlanValidationAction.NEEDS_INPUT, safe_message="指定菜谱信息不完整，请重新选择。")
        if (required_food_id is None) != (required_catalog_version is None):
            return MealCompositionResult(action=PlanValidationAction.NEEDS_INPUT, safe_message="指定菜品版本无效，请重新选择。")
        if required_food_id is not None:
            assert required_catalog_version is not None
            qualified = self._nutrition_port.calculate_nutrition(
                NutritionCalculationInput(food_id=required_food_id, catalog_version=required_catalog_version, grams=Decimal("1"))
            )
            if qualified.action is not NutritionAction.PASS:
                return MealCompositionResult(action=PlanValidationAction.NEEDS_INPUT, safe_message="所选菜品已不再可用，请重新选择。")
        recent_recipe_ids = () if user_id is None else self._repository.list_recent_recipe_ids(
            user_id=user_id, plan_limit=3
        )
        if self._repository.has_managed_recipe_candidates() or required_food_id is not None:
            candidates = (
                candidate
                for slot in REQUIRED_MEAL_SLOTS
                if slot not in {meal.slot for meal in fixed_meals}
                for candidate in self._scan_recipes(
                    self._repository.list_managed_recipe_candidates,
                    catalog_version=(required_catalog_version if slot is required_slot and required_food_id is not None else catalog_version),
                    meal_slot=slot,
                    stats=diagnostics.slots[slot],
                    food_ids=(required_food_id,) if slot is required_slot and required_food_id is not None else None,
                    recipe_id=required_recipe_id if slot is required_slot else None,
                    recipe_revision=required_recipe_revision if slot is required_slot else None,
                    include_components=self._selection_policy.bundle_enabled and slot in BUNDLE_SLOTS and required_food_id is None,
                )
            )
            return self._compose_managed_candidates(
                candidates, preferences, exclude_recipe_ids, recent_recipe_ids, required_food_id, required_catalog_version, required_slot,
                target=target, fixed_meals=fixed_meals, feedback_intent=feedback_intent,
                required_recipe_id=required_recipe_id, diagnostics=diagnostics,
            )

        def controlled_options() -> Iterator[SelectionCandidate]:
            for slot in REQUIRED_MEAL_SLOTS:
                if slot in {meal.slot for meal in fixed_meals}:
                    continue
                for recipe in self._scan_recipes(
                    self._repository.list_controlled_recipes,
                    catalog_version=catalog_version, recipe_version=recipe_version, meal_slot=slot,
                    stats=diagnostics.slots[slot],
                ):
                    stats = diagnostics.slots[slot]
                    if recipe.id in exclude_recipe_ids:
                        stats.filtered += 1
                        continue
                    if self._matches_exclusion(recipe=recipe, exclusions=preferences.exclusions):
                        stats.excluded += 1
                        continue
                    if feedback_intent == "lighter" and slot is required_slot and "清淡" not in {normalized_label(tag) for tag in recipe.flavour_tags}:
                        stats.filtered += 1
                        continue
                    built = self._build_meal(recipe=recipe, slot=slot, preferences=preferences, stats=stats)
                    if built is not None:
                        food_ids = frozenset(ingredient.food_id for ingredient in recipe.ingredients)
                        yield SelectionCandidate(built, food_ids)
                        grams = self._adapted_portion(built, target, fixed_meals)
                        if grams is not None:
                            adjusted = self._build_meal(recipe=recipe, slot=slot, preferences=preferences, stats=stats, portion_grams=grams)
                            if adjusted is not None:
                                yield SelectionCandidate(adjusted, food_ids)

        meals = self._select_meals(options=controlled_options(), target=target, preferences=preferences, fixed_meals=fixed_meals, recent_recipe_ids=recent_recipe_ids, diagnostics=diagnostics)
        if not meals:
            return self._search_failure(diagnostics, fixed_meals)
        return MealCompositionResult(
            action=PlanValidationAction.PASS, meals=meals,
            safe_message="三餐营养值已由合格目录条目和受控克数重新计算。",
        )

    def _scan_recipes(self, loader: Callable, *, stats: SlotDiagnostics | None = None, **filters) -> Iterator:
        """One slot gets its own budget; exhaustion never rejects other slots.

        Time limits are cooperative: a synchronous database call already in flight
        finishes before the next check. Count limits still bound calls and memory.
        """
        stats = stats or SlotDiagnostics()
        budget = self._search_budget
        started = self._clock()
        deadline = started + budget.scan_seconds_per_slot
        after_id = None
        try:
            while stats.scanned < budget.scan_per_slot:
                if self._clock() >= deadline:
                    stats.stop = ScanStop.TIME
                    return
                size = min(budget.batch_size, budget.scan_per_slot - stats.scanned)
                page = loader(**filters, after_id=after_id, limit=size)
                stats.pages += 1
                stats.fetched += len(page)
                if not page:
                    stats.stop = ScanStop.EXHAUSTED
                    return
                for recipe in page:
                    if self._clock() >= deadline:
                        stats.stop = ScanStop.TIME
                        return
                    stats.scanned += 1
                    yield recipe
                after_id = page[-1].id
                if len(page) < size:
                    stats.stop = ScanStop.EXHAUSTED
                    return
            # No extra read to prove whether more rows exist: hitting the count
            # budget means the catalog may have unvisited candidates.
            stats.stop = ScanStop.COUNT
        finally:
            stats.elapsed_ms = max(0, int((self._clock() - started) * 1000))

    @staticmethod
    def _search_failure(diagnostics: SearchDiagnostics, fixed_meals: tuple[PlannedMeal, ...]) -> MealCompositionResult:
        fixed = {meal.slot for meal in fixed_meals}
        missing = [slot for slot in REQUIRED_MEAL_SLOTS if slot not in fixed and not diagnostics.slots[slot].shortlisted]
        names = "、".join({MealSlot.BREAKFAST: "早餐", MealSlot.LUNCH: "午餐", MealSlot.DINNER: "晚餐"}[slot] for slot in missing)
        affected = [diagnostics.slots[slot] for slot in missing]
        reason = CompositionFailureReason.NO_COMBINATION
        message = "本次候选无法组成不重复的完整三餐，请更换菜品或调整偏好。"
        if any(item.stop in {ScanStop.TIME, ScanStop.COUNT} or item.bundle_stop in {ScanStop.TIME, ScanStop.COUNT} for item in affected) or diagnostics.combination_stop in {ScanStop.TIME, ScanStop.COUNT}:
            reason = CompositionFailureReason.SEARCH_BUDGET
            message = "本次筛选时间或计算额度已用完，尚未找到完整餐单。请稍后重试；若反复出现，请联系管理员调整筛选预算。"
        elif missing:
            if any(item.unavailable for item in affected):
                reason = CompositionFailureReason.NUTRITION_UNAVAILABLE
                message = f"{names}缺少可用候选，其中部分候选营养数据当前不可用。请稍后重试或联系管理员检查菜谱目录。"
            elif any(item.excluded for item in affected):
                reason = CompositionFailureReason.EXCLUSIONS
                message = f"按已确认的忌口筛选后，{names}没有可用候选。请核对饮食偏好，或联系管理员补充合适菜谱；系统不会自动放宽忌口。"
            else:
                reason = CompositionFailureReason.MISSING_SLOT
                message = f"{names}没有满足当前要求的可用候选。请更换菜品，或联系管理员补充、启用合格菜谱。"
        return MealCompositionResult(action=PlanValidationAction.REPLAN, failure_reason=reason, safe_message=message)

    def list_replacement_recipes(
        self, *, food_id: uuid.UUID, catalog_version: str, affected_slot: MealSlot,
        exclude_recipe_ids: tuple[uuid.UUID, ...], preferences: PreferenceReview,
    ) -> tuple[ManagedRecipeCandidate, ...]:
        """Offer bounded, stable, currently usable recipes for one confirmed food."""
        if not preferences.confirmed:
            return ()
        candidates = (
            item for item in self._scan_recipes(self._repository.list_managed_recipe_candidates, catalog_version=catalog_version, meal_slot=affected_slot, food_ids=(food_id,))
            if item.nutrition_item_id == food_id and item.catalog_version == catalog_version
            and item.meal_slot is affected_slot and item.id not in exclude_recipe_ids
            and self._build_managed_meal(item, preferences) is not None
        )
        # SQL already orders by UUID; stop after 20 usable choices without
        # materializing or calculating all remaining recipes for this food.
        return tuple(islice(candidates, 20))

    def keep_replaceable_food_identities(
        self,
        *,
        identities: tuple[tuple[uuid.UUID, str], ...],
        affected_slot: MealSlot,
        exclude_recipe_ids: tuple[uuid.UUID, ...],
        preferences: PreferenceReview,
    ) -> tuple[tuple[uuid.UUID, str], ...]:
        """Keep only catalog identities backed by a usable managed recipe for this slot."""

        requested = set(identities)
        eligible = {
            (candidate.nutrition_item_id, candidate.catalog_version)
            for candidate in self._scan_recipes(self._repository.list_managed_recipe_candidates, catalog_version=None, meal_slot=affected_slot, food_ids=tuple(identity[0] for identity in identities))
            if candidate.meal_slot is affected_slot
            and candidate.id not in exclude_recipe_ids
            and (candidate.nutrition_item_id, candidate.catalog_version) in requested
            and self._build_managed_meal(candidate, preferences) is not None
        }
        return tuple(identity for identity in identities if identity in eligible)

    def _compose_managed_candidates(
        self,
        candidates: Iterable[ManagedRecipeCandidate],
        preferences: PreferenceReview,
        exclude_recipe_ids: tuple[uuid.UUID, ...],
        recent_recipe_ids: tuple[uuid.UUID, ...],
        required_food_id: uuid.UUID | None = None,
        required_catalog_version: str | None = None,
        required_slot: MealSlot | None = None,
        *,
        target: DailyTarget | None = None,
        fixed_meals: tuple[PlannedMeal, ...] = (),
        feedback_intent: str | None = None,
        required_recipe_id: uuid.UUID | None = None,
        diagnostics: SearchDiagnostics,
    ) -> MealCompositionResult:
        fixed_slots = {meal.slot for meal in fixed_meals}
        bundles = {
            slot: BundlePool(slot=slot, energy=self._slot_energy(target, fixed_meals, slot),
                             policy=self._selection_policy, preferences=preferences,
                             recent=recent_recipe_ids, stats=diagnostics.slots[slot], clock=self._clock)
            for slot in BUNDLE_SLOTS if slot not in fixed_slots
            and self._selection_policy.bundle_enabled and required_food_id is None
        }
        def adapt_component(candidate: ManagedRecipeCandidate, meal: PlannedMeal, energy: Decimal) -> PlannedMeal | None:
            grams = self._portion_for_energy(meal, energy)
            if grams is None:
                return meal
            return self._build_managed_meal(candidate, preferences, stats=diagnostics.slots[candidate.meal_slot],
                                            portion_grams=grams, allow_component=True)

        def options() -> Iterator[SelectionCandidate]:
            for candidate in candidates:
                stats = diagnostics.slots[candidate.meal_slot]
                if candidate.meal_slot in fixed_slots or candidate.id in exclude_recipe_ids or (
                    required_food_id is not None and candidate.meal_slot is required_slot
                    and (candidate.nutrition_item_id != required_food_id or candidate.catalog_version != required_catalog_version)
                ) or (feedback_intent == "lighter" and candidate.meal_slot is required_slot and "清淡" not in {normalized_label(tag) for tag in candidate.flavour_tags}):
                    stats.filtered += 1
                    continue
                if candidate.meal_role != "standalone":
                    if candidate.meal_slot in bundles and candidate.meal_role in BUNDLE_ROLES:
                        meal = self._build_managed_meal(candidate, preferences, stats=stats, allow_component=True)
                        if meal is not None:
                            bundles[candidate.meal_slot].add(candidate, meal)
                    else:
                        stats.filtered += 1
                    continue
                meal = self._build_managed_meal(candidate, preferences, stats=stats)
                if meal is not None:
                    food_ids = frozenset((candidate.nutrition_item_id,))
                    yield SelectionCandidate(meal, food_ids)
                    grams = self._adapted_portion(meal, target, fixed_meals)
                    if grams is not None:
                        adjusted = self._build_managed_meal(candidate, preferences, stats=stats, portion_grams=grams)
                        if adjusted is not None:
                            yield SelectionCandidate(adjusted, food_ids)
            for pool in bundles.values():
                yield from pool.finish(excluded=exclude_recipe_ids, adapt=adapt_component)
        meals = self._select_meals(options=options(), target=target, preferences=preferences, recent_recipe_ids=recent_recipe_ids, fixed_meals=fixed_meals, diagnostics=diagnostics)
        if not meals:
            failure = self._search_failure(diagnostics, fixed_meals)
            if required_recipe_id is not None and failure.failure_reason is not CompositionFailureReason.SEARCH_BUDGET:
                return MealCompositionResult(action=PlanValidationAction.NEEDS_INPUT, failure_reason=failure.failure_reason, safe_message="所选菜谱已变更、停用或暂不可用，请重新选择。")
            if feedback_intent == "lighter" and failure.failure_reason is not CompositionFailureReason.SEARCH_BUDGET:
                return failure.model_copy(update={"safe_message": "本次未找到符合忌口且标记为清淡的替换菜品，请更换菜品或联系管理员补充菜谱。"})
            return failure
        return MealCompositionResult(action=PlanValidationAction.PASS, meals=meals, safe_message="餐单营养值已按候选关联目录的每 100 克基准重算。")

    def _select_meals(
        self, *, options: Iterable[PlannedMeal | SelectionCandidate], target: DailyTarget | None,
        preferences: PreferenceReview, recent_recipe_ids: tuple[uuid.UUID, ...] = (),
        fixed_meals: tuple[PlannedMeal, ...] = (),
        diagnostics: SearchDiagnostics | None = None,
    ) -> tuple[PlannedMeal, ...]:
        diagnostics = diagnostics or SearchDiagnostics()
        def validation_rank(meals: tuple[PlannedMeal, ...]) -> int:
            assert target is not None
            result = self.validate_plan(target=target, meals=meals, allow_target_relaxation=True)
            if result.action is PlanValidationAction.PASS:
                diagnostics.validation_pass += 1
            elif result.action is PlanValidationAction.RELAX:
                diagnostics.validation_relax += 1
            else:
                diagnostics.validation_rejected += 1
            return {PlanValidationAction.PASS: 0, PlanValidationAction.RELAX: 1}.get(result.action, 2)

        return select_meals(options=options, target=target, preferences=preferences,
                            recent_recipe_ids=recent_recipe_ids, fixed_meals=fixed_meals,
                            validation_rank=validation_rank, budget=self._search_budget, policy=self._selection_policy, clock=self._clock, diagnostics=diagnostics)

    def _slot_energy(self, target: DailyTarget | None, fixed_meals: tuple[PlannedMeal, ...], slot: MealSlot) -> Decimal | None:
        if target is None:
            return None
        fixed_slots = {meal.slot for meal in fixed_meals}
        slots = [item for item in REQUIRED_MEAL_SLOTS if item not in fixed_slots]
        if slot not in slots:
            return None
        residual = max(Decimal(0), (target.energy_kcal.lower + target.energy_kcal.upper) / 2
                       - sum((meal.nutrients.energy_kcal for meal in fixed_meals), Decimal(0)))
        return residual * self._selection_policy.weight(slot) / sum(self._selection_policy.weight(item) for item in slots)

    def _adapted_portion(self, meal: PlannedMeal, target: DailyTarget | None, fixed_meals: tuple[PlannedMeal, ...]) -> Decimal | None:
        return self._portion_for_energy(meal, self._slot_energy(target, fixed_meals, meal.slot))

    def _portion_for_energy(self, meal: PlannedMeal, energy: Decimal | None) -> Decimal | None:
        policy = self._selection_policy
        if not policy.portion_adjustment_enabled or energy is None or meal.nutrients.energy_kcal <= 0:
            return None
        desired = meal.portion_grams * energy / meal.nutrients.energy_kcal
        # Whole grams keep the displayed quantity and the calculator input aligned.
        lower = (meal.portion_grams * policy.portion_min_multiplier).to_integral_value(rounding=ROUND_CEILING)
        upper = min(Decimal("2000"), meal.portion_grams * policy.portion_max_multiplier).to_integral_value(rounding=ROUND_FLOOR)
        if lower > upper or upper <= 0:
            return None
        grams = max(lower, min(upper, desired.to_integral_value(rounding=ROUND_HALF_UP)))
        return grams if grams > 0 and grams != meal.portion_grams else None

    @staticmethod
    def _portion_description(original: str, base: Decimal, grams: Decimal) -> str:
        if grams == base:
            return original
        # Do not retain household-unit counts such as “4 dumplings” after scaling.
        return f"按目标调整份量（原份量 {base.normalize():f}g）"

    def _build_managed_meal(self, candidate, preferences: PreferenceReview, *, stats: SlotDiagnostics | None = None, portion_grams: Decimal | None = None, allow_component: bool = False) -> PlannedMeal | None:
        stats = stats or SlotDiagnostics()
        if candidate.meal_role != "standalone" and not (allow_component and candidate.meal_role in BUNDLE_ROLES):
            stats.filtered += 1
            return None
        # Cheap known-label exclusions precede nutrition I/O. Canonical aliases
        # are still checked after the authoritative catalog lookup below.
        if matches_exclusion(preferences.exclusions, (candidate.display_name, *candidate.method_tags, *candidate.flavour_tags)):
            stats.excluded += 1
            return None
        stats.nutrition_calls += 1
        grams = candidate.portion_grams if portion_grams is None else portion_grams
        calculation = self._nutrition_port.calculate_nutrition(NutritionCalculationInput(food_id=candidate.nutrition_item_id, catalog_version=candidate.catalog_version, grams=grams))
        if calculation.action is not NutritionAction.PASS or calculation.food is None or calculation.nutrients is None:
            stats.unavailable += 1
            return None
        if matches_exclusion(preferences.exclusions, (calculation.food.canonical_name, *calculation.food.aliases, candidate.display_name, *candidate.method_tags, *candidate.flavour_tags)):
            stats.excluded += 1
            return None
        if portion_grams is None:
            stats.eligible += 1
        summaries = tuple(f"偏好：{value}" for value in preferences.taste_preferences if normalized_label(value) in {normalized_label(tag) for tag in (*candidate.flavour_tags, *candidate.method_tags)})
        return PlannedMeal(slot=candidate.meal_slot, recipe_id=candidate.id, display_name=candidate.display_name, portion_description=self._portion_description(candidate.portion_description, candidate.portion_grams, grams), portion_grams=grams, method_tags=candidate.method_tags, flavour_tags=candidate.flavour_tags, matched_preference_summaries=summaries, nutrients=PlanningNutritionValues(**calculation.nutrients.model_dump()))

    def _build_meal(self, *, recipe, slot: MealSlot, preferences: PreferenceReview, stats: SlotDiagnostics | None = None, portion_grams: Decimal | None = None) -> PlannedMeal | None:
        stats = stats or SlotDiagnostics()
        grams = recipe.portion_grams if portion_grams is None else portion_grams
        factor = grams / recipe.portion_grams
        calculated: list[NutritionValues] = []
        for ingredient in recipe.ingredients:
            stats.nutrition_calls += 1
            calculation = self._nutrition_port.calculate_nutrition(
                NutritionCalculationInput(
                    food_id=ingredient.food_id,
                    catalog_version=ingredient.catalog_version,
                    grams=ingredient.grams * factor,
                )
            )
            if calculation.action is not NutritionAction.PASS:
                stats.unavailable += 1
                return None
            assert calculation.food is not None
            assert calculation.nutrients is not None
            if matches_exclusion(preferences.exclusions, (calculation.food.canonical_name, *calculation.food.aliases)):
                stats.excluded += 1
                return None
            calculated.append(calculation.nutrients)
        if not calculated:
            return None
        if portion_grams is None:
            stats.eligible += 1
        preference_summaries = tuple(
            f"偏好：{preference}"
            for preference in self._matching_preferences(recipe=recipe, preferences=preferences)
        )
        return PlannedMeal(
            slot=slot,
            recipe_id=recipe.id,
            display_name=recipe.display_name,
            portion_description=self._portion_description(recipe.portion_description, recipe.portion_grams, grams),
            portion_grams=grams,
            method_tags=recipe.method_tags,
            flavour_tags=recipe.flavour_tags,
            matched_preference_summaries=preference_summaries,
            matched_exclusion_summaries=(),
            nutrients=PlanningNutritionValues(
                energy_kcal=sum((value.energy_kcal for value in calculated), Decimal("0")),
                protein_g=sum((value.protein_g for value in calculated), Decimal("0")),
                fat_g=sum((value.fat_g for value in calculated), Decimal("0")),
                carbohydrate_g=sum(
                    (value.carbohydrate_g for value in calculated), Decimal("0")
                ),
            ),
        )

    @staticmethod
    def _matches_exclusion(*, recipe, exclusions: tuple[str, ...]) -> bool:
        return matches_exclusion(exclusions, (recipe.display_name, *recipe.method_tags, *recipe.flavour_tags))

    @staticmethod
    def _matching_preferences(*, recipe, preferences: PreferenceReview) -> tuple[str, ...]:
        # The public card only claims a preference when it is literally present in controlled tags.
        return tuple(
            preference
            for preference in preferences.taste_preferences
            if preference.casefold() in {tag.casefold() for tag in recipe.flavour_tags}
        )

    @staticmethod
    def _daily_totals(meals: tuple[PlannedMeal, ...]) -> PlanningNutritionValues:
        return PlanningNutritionValues(
            energy_kcal=sum((meal.nutrients.energy_kcal for meal in meals), Decimal("0")),
            protein_g=sum((meal.nutrients.protein_g for meal in meals), Decimal("0")),
            fat_g=sum((meal.nutrients.fat_g for meal in meals), Decimal("0")),
            carbohydrate_g=sum(
                (meal.nutrients.carbohydrate_g for meal in meals), Decimal("0")
            ),
        )

    @staticmethod
    def _first_failed_target_metric(
        *, target: DailyTarget, totals: PlanningNutritionValues
    ) -> str | None:
        for field in ("energy_kcal", "carbohydrate_g", "protein_g", "fat_g"):
            bounds = getattr(target, field)
            value = getattr(totals, field)
            if value < bounds.lower or value > bounds.upper:
                return field
        return None

    @staticmethod
    def _first_failed_macro_ratio(totals: PlanningNutritionValues) -> str | None:
        if totals.energy_kcal <= 0:
            return "energy_kcal"
        for field, kcal_per_gram, bounds in (
            ("carbohydrate_g", Decimal("4"), CARBOHYDRATE_AMDR),
            ("protein_g", Decimal("4"), PROTEIN_AMDR),
            ("fat_g", Decimal("9"), FAT_AMDR),
        ):
            ratio = getattr(totals, field) * kcal_per_gram / totals.energy_kcal
            if ratio < bounds[0] or ratio > bounds[1]:
                return f"{field}-ratio"
        return None

    @staticmethod
    def _has_complete_inputs(profile: PlanningProfileInput, preferences: PreferenceReview) -> bool:
        return all(
            (
                profile.height_cm is not None,
                profile.weight_kg is not None,
                profile.age_years is not None,
                profile.formula_variant is not None,
                profile.activity_level is not None,
                profile.goal is not None,
                profile.goal_speed is not None,
                preferences.confirmed,
            )
        )

    @staticmethod
    def _is_health_scope_blocked(profile: PlanningProfileInput) -> bool:
        return any(
            (
                profile.age_years is not None
                and not MIN_ADULT_AGE <= profile.age_years <= MAX_ADULT_AGE,
                profile.is_pregnant_or_breastfeeding,
                profile.has_disease_or_treatment,
                profile.uses_medication,
                profile.has_eating_disorder_or_self_harm_risk,
                profile.has_extreme_weight_control_goal,
                profile.goal not in {PlanningGoal.MAINTAIN, PlanningGoal.LOSS, PlanningGoal.GAIN},
                profile.goal_speed not in SPEED_DELTAS,
            )
        )

    @staticmethod
    def _mifflin_st_jeor(profile: PlanningProfileInput) -> Decimal:
        """Use the explicit selected variant; it is a formula parameter, not an identity claim."""

        assert profile.weight_kg is not None
        assert profile.height_cm is not None
        assert profile.age_years is not None
        assert profile.formula_variant is not None
        base = (
            Decimal("10") * profile.weight_kg
            + Decimal("6.25") * profile.height_cm
            - Decimal("5") * Decimal(profile.age_years)
        )
        if profile.formula_variant is FormulaVariant.MIFFLIN_ST_JEOR_MALE:
            return base + Decimal("5")
        return base - Decimal("161")

    @staticmethod
    def _macro_range(
        energy: TargetRange, percentage: tuple[Decimal, Decimal], kcal_per_gram: Decimal
    ) -> TargetRange:
        return TargetRange(
            lower=energy.lower * percentage[0] / kcal_per_gram,
            upper=energy.upper * percentage[1] / kcal_per_gram,
        )


class PlanningProfileUnavailable(LookupError):
    """Uniform missing, foreign, and deleted profile result."""


class PlanningCompletionProjectionService:
    """Creates a dashboard fact only after the Agent boundary proves validated completion."""

    def __init__(
        self,
        *,
        repository: PlanningCompletionProjectionRepository,
        now: Callable[[], datetime] | None = None,
        commit: Callable[[], None] | None = None,
        rollback: Callable[[], None] | None = None,
    ) -> None:
        self._repository = repository
        self._now = now or (lambda: datetime.now(UTC))
        self._commit = commit or (lambda: None)
        self._rollback = rollback or (lambda: None)

    def record_validated_completion(
        self, *, user_id: uuid.UUID, run_id: uuid.UUID, thread_id: uuid.UUID, target: DailyTarget
    ) -> PlanningCompletionProjection:
        existing = self._repository.get_completion_projection_for_run_for_user(
            user_id=user_id, run_id=run_id, for_update=True
        )
        if existing is not None:
            return existing
        profile = self._repository.get_profile_for_user(user_id=user_id, for_update=True)
        if profile is None:
            raise PlanningProfileUnavailable("planning profile is unavailable for completed plan")
        projection = PlanningCompletionProjection(
            id=uuid.uuid4(), user_id=user_id, profile_id=profile.id, completed_run_id=run_id,
            completed_thread_id=thread_id, profile_revision=profile.revision,
            target_version=profile.target_policy_version,
            energy_kcal_lower=target.energy_kcal.lower, energy_kcal_upper=target.energy_kcal.upper,
            carbohydrate_g_lower=target.carbohydrate_g.lower, carbohydrate_g_upper=target.carbohydrate_g.upper,
            protein_g_lower=target.protein_g.lower, protein_g_upper=target.protein_g.upper,
            fat_g_lower=target.fat_g.lower, fat_g_upper=target.fat_g.upper,
            completed_at=self._now(), revoked_at=None, revocation_reason=None,
        )
        try:
            projection = self._repository.add_completion_projection(projection)
            self._commit()
            return projection
        except Exception:
            self._rollback()
            raise


class PlanningProfileService:
    """Owns explicit profile save/delete transactions, not policy or memory preferences."""

    def __init__(self, *, repository: PlanningProfileRepository, completion_repository: PlanningCompletionProjectionRepository | None = None, now: Callable[[], datetime] | None = None, commit: Callable[[], None] | None = None, rollback: Callable[[], None] | None = None) -> None:
        self._repository = repository
        self._completion_repository = completion_repository or repository
        self._now = now or (lambda: datetime.now(UTC))
        self._commit = commit or (lambda: None)
        self._rollback = rollback or (lambda: None)

    def get_profile(self, *, user_id: uuid.UUID) -> PlanningProfile:
        profile = self._repository.get_profile_for_user(user_id=user_id)
        if profile is None:
            raise PlanningProfileUnavailable("planning profile is unavailable")
        return profile

    def replace_profile(self, *, user_id: uuid.UUID, payload: PlanningProfileWrite) -> PlanningProfile:
        profile = self._repository.get_profile_for_user(user_id=user_id, for_update=True)
        now = self._now()
        try:
            if profile is None:
                profile = PlanningProfile(
                    id=uuid.uuid4(), user_id=user_id, target_policy_version=TARGET_POLICY_VERSION,
                    formula_version=FORMULA_VERSION, revision=1, created_at=now, updated_at=now, deleted_at=None,
                    **payload.model_dump(),
                )
                profile = self._repository.add_profile(profile)
            else:
                self._apply_payload(profile, payload.model_dump())
                profile.target_policy_version = TARGET_POLICY_VERSION
                profile.formula_version = FORMULA_VERSION
                profile.revision += 1
                profile.updated_at = now
                self._revoke_completion(user_id=user_id, reason="profile_revision_changed", revoked_at=now)
            self._commit()
            return profile
        except Exception:
            self._rollback()
            raise

    def update_profile(self, *, user_id: uuid.UUID, payload: PlanningProfilePatch) -> PlanningProfile:
        profile = self._repository.get_profile_for_user(user_id=user_id, for_update=True)
        if profile is None:
            raise PlanningProfileUnavailable("planning profile is unavailable")
        try:
            self._apply_payload(profile, payload.model_dump(exclude_unset=True))
            profile.revision += 1
            profile.updated_at = self._now()
            self._revoke_completion(user_id=user_id, reason="profile_revision_changed", revoked_at=profile.updated_at)
            self._commit()
            return profile
        except Exception:
            self._rollback()
            raise

    def delete_profile(self, *, user_id: uuid.UUID) -> None:
        profile = self._repository.get_profile_for_user(user_id=user_id, for_update=True)
        if profile is None:
            raise PlanningProfileUnavailable("planning profile is unavailable")
        now = self._now()
        try:
            profile.deleted_at = now
            profile.updated_at = now
            self._revoke_completion(user_id=user_id, reason="profile_deleted", revoked_at=now)
            self._commit()
        except Exception:
            self._rollback()
            raise

    @staticmethod
    def _apply_payload(profile: PlanningProfile, values: dict[str, object]) -> None:
        for field, value in values.items():
            setattr(profile, field, value.value if hasattr(value, "value") else value)

    def _revoke_completion(self, *, user_id: uuid.UUID, reason: str, revoked_at: datetime) -> None:
        revoke = getattr(self._completion_repository, "revoke_completion_projection_for_user", None)
        if callable(revoke):
            revoke(user_id=user_id, reason=reason, revoked_at=revoked_at)
