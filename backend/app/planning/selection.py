"""Bounded, deterministic ranking of catalog-calculated meal combinations."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Iterable
from decimal import Decimal
from itertools import product
from uuid import UUID
from time import monotonic

from pydantic import BaseModel, ConfigDict, Field

from app.planning.diagnostics import SearchDiagnostics, ScanStop
from app.planning.schemas import (
    DailyTarget,
    PlannedMeal,
    PreferenceReview,
    REQUIRED_MEAL_SLOTS,
)


SELECTION_POLICY_VERSION = "planning-selection.v5"


class PlanningSearchBudget(BaseModel):
    """Operator-controlled work budgets, independent of catalog size."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    batch_size: int = Field(default=64, ge=1, le=512)
    scan_per_slot: int = Field(default=2048, ge=1, le=100000)
    options_per_slot: int = Field(default=12, ge=1, le=64)
    max_combinations: int = Field(default=1728, ge=1, le=262144)
    scan_seconds_per_slot: float = Field(default=3, gt=0, le=30, allow_inf_nan=False)
    combination_seconds: float = Field(default=2, gt=0, le=30, allow_inf_nan=False)


_METRICS = ("energy_kcal", "protein_g", "fat_g", "carbohydrate_g")


def normalized_label(value: str) -> str:
    return "".join(unicodedata.normalize("NFKC", value).casefold().split())


def matches_exclusion(exclusions: tuple[str, ...], labels: tuple[str, ...]) -> bool:
    """Use controlled aliases as well as display labels; never infer missing ingredients."""

    normalized_labels = tuple(normalized_label(label) for label in labels)
    for exclusion in exclusions:
        # Preserve clause boundaries before removing whitespace: “不吃辣 饮食清淡”
        # contains an exclusion and a preference, not the food name “辣饮食清淡”.
        clauses = re.split(r"[，。；,;\n]+|(?<=[\u3400-\u9fff])\s+|\s+(?=[\u3400-\u9fff])", exclusion)
        for clause in clauses:
            term = normalized_label(clause)
            for prefix in ("不要吃", "不能吃", "不吃", "不要", "避免"):
                if term.startswith(prefix):
                    term = term[len(prefix) :]
                    break
            if term and any(term in label for label in normalized_labels):
                return True
    return False


def preference_matches(meal: PlannedMeal, preferences: PreferenceReview) -> int:
    tags = {normalized_label(tag) for tag in (*meal.flavour_tags, *meal.method_tags)}
    return sum(
        normalized_label(value) in tags for value in preferences.taste_preferences
    )


def _distance(
    meals: tuple[PlannedMeal, ...], target: DailyTarget
) -> tuple[Decimal, Decimal]:
    outside = Decimal(0)
    midpoint = Decimal(0)
    for metric in _METRICS:
        bounds = getattr(target, metric)
        value = sum((getattr(meal.nutrients, metric) for meal in meals), Decimal(0))
        center = (bounds.lower + bounds.upper) / 2
        denominator = max(center, Decimal(1))
        outside += (
            max(bounds.lower - value, value - bounds.upper, Decimal(0)) / denominator
        )
        midpoint += abs(value - center) / denominator
    return outside, midpoint


def select_meals(
    *,
    options: Iterable[PlannedMeal],
    target: DailyTarget | None,
    preferences: PreferenceReview,
    recent_recipe_ids: tuple[UUID, ...],
    fixed_meals: tuple[PlannedMeal, ...],
    validation_rank: Callable[[tuple[PlannedMeal, ...]], int],
    budget: PlanningSearchBudget | None = None,
    clock: Callable[[], float] = monotonic,
    diagnostics: SearchDiagnostics | None = None,
) -> tuple[PlannedMeal, ...]:
    """Stream a bounded shortlist, then search within count and cooperative time limits.

    Shortlisting is a bounded heuristic, not a claim of globally optimal nutrition.
    A previously used recipe remains eligible when it is the only valid solution.
    """

    diagnostics = diagnostics or SearchDiagnostics()
    budget = budget or PlanningSearchBudget()
    fixed = {meal.slot: meal for meal in fixed_meals}
    fixed_ids = {meal.recipe_id for meal in fixed_meals}
    recent = set(recent_recipe_ids)
    variable_count = len(REQUIRED_MEAL_SLOTS) - len(
        set(fixed) & set(REQUIRED_MEAL_SLOTS)
    )

    def shortlist_key(meal: PlannedMeal) -> tuple:
        residual_distance = Decimal(0)
        if target is not None and variable_count:
            for metric in _METRICS:
                bounds = getattr(target, metric)
                center = (bounds.lower + bounds.upper) / 2
                consumed = sum(
                    (getattr(item.nutrients, metric) for item in fixed_meals),
                    Decimal(0),
                )
                residual_distance += abs(
                    getattr(meal.nutrients, metric)
                    - (center - consumed) / variable_count
                ) / max(center, Decimal(1))
        return (
            residual_distance,
            -preference_matches(meal, preferences),
            meal.recipe_id in recent,
            str(meal.recipe_id),
        )

    # Keep only K values per slot even when the input spans many database pages.
    shortlists: dict = {slot: [] for slot in REQUIRED_MEAL_SLOTS if slot not in fixed}
    for meal in options:
        if meal.slot not in shortlists or meal.recipe_id in fixed_ids:
            continue
        pool = shortlists[meal.slot]
        pool.append(meal)
        pool.sort(key=shortlist_key)
        del pool[budget.options_per_slot:]
    for slot, pool in shortlists.items():
        diagnostics.slots[slot].shortlisted = len(pool)
    pools = []
    for slot in REQUIRED_MEAL_SLOTS:
        pool = (fixed[slot],) if slot in fixed else tuple(shortlists[slot])
        if not pool:
            return ()
        pools.append(pool)

    extra_fixed = tuple(
        meal for meal in fixed_meals if meal.slot not in REQUIRED_MEAL_SLOTS
    )

    def score(meals: tuple[PlannedMeal, ...]) -> tuple:
        outside, midpoint = (
            (Decimal(0), Decimal(0)) if target is None else _distance(meals, target)
        )
        return (
            validation_rank(meals) if target is not None else 0,
            outside,
            -sum(preference_matches(meal, preferences) for meal in meals),
            sum(meal.recipe_id in recent for meal in meals),
            midpoint,
            tuple(str(meal.recipe_id) for meal in meals),
        )

    started = clock()
    deadline = started + budget.combination_seconds
    best: tuple[PlannedMeal, ...] = ()
    best_score: tuple | None = None
    for index, combination in enumerate(product(*pools)):
        # Count attempts, including duplicate-recipe combinations, to bound all work.
        if index >= budget.max_combinations:
            diagnostics.combination_stop = ScanStop.COUNT
            break
        if clock() >= deadline:
            diagnostics.combination_stop = ScanStop.TIME
            break
        diagnostics.combinations += 1
        meals = (*combination, *extra_fixed)
        if len({meal.recipe_id for meal in meals}) != len(meals):
            diagnostics.duplicate_combinations += 1
            continue
        rank = score(meals)
        if best_score is None or rank < best_score:
            best, best_score = meals, rank
    else:
        diagnostics.combination_stop = ScanStop.EXHAUSTED
    diagnostics.combination_elapsed_ms = max(0, int((clock() - started) * 1000))
    return best
