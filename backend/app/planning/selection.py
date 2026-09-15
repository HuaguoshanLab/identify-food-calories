"""Bounded, deterministic ranking of catalog-calculated meal combinations."""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from decimal import Decimal
from itertools import product
from uuid import UUID

from app.planning.schemas import (
    DailyTarget,
    PlannedMeal,
    PreferenceReview,
    REQUIRED_MEAL_SLOTS,
)


SELECTION_POLICY_VERSION = "planning-selection.v2"
MAX_RECIPE_CANDIDATES = 256
MAX_OPTIONS_PER_SLOT = 12
_METRICS = ("energy_kcal", "protein_g", "fat_g", "carbohydrate_g")


def normalized_label(value: str) -> str:
    return "".join(unicodedata.normalize("NFKC", value).casefold().split())


def matches_exclusion(exclusions: tuple[str, ...], labels: tuple[str, ...]) -> bool:
    """Use controlled aliases as well as display labels; never infer missing ingredients."""

    normalized_labels = tuple(normalized_label(label) for label in labels)
    for exclusion in exclusions:
        term = normalized_label(exclusion)
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
    options: tuple[PlannedMeal, ...],
    target: DailyTarget | None,
    preferences: PreferenceReview,
    recent_recipe_ids: tuple[UUID, ...],
    fixed_meals: tuple[PlannedMeal, ...],
    validation_rank: Callable[[tuple[PlannedMeal, ...]], int],
) -> tuple[PlannedMeal, ...]:
    """Search at most 12³ combinations. Existing meal snapshots are never rewritten.

    Shortlisting is a bounded heuristic, not a claim of globally optimal nutrition.
    A previously used recipe remains eligible when it is the only valid solution.
    """

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

    pools: list[tuple[PlannedMeal, ...]] = []
    for slot in REQUIRED_MEAL_SLOTS:
        if slot in fixed:
            pools.append((fixed[slot],))
            continue
        pool = tuple(
            sorted(
                (
                    meal
                    for meal in options
                    if meal.slot is slot and meal.recipe_id not in fixed_ids
                ),
                key=shortlist_key,
            )[:MAX_OPTIONS_PER_SLOT]
        )
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

    combinations = (
        (*combination, *extra_fixed)
        for combination in product(*pools)
        if len({meal.recipe_id for meal in (*combination, *extra_fixed)})
        == len(combination) + len(extra_fixed)
    )
    return min(combinations, key=score, default=())
