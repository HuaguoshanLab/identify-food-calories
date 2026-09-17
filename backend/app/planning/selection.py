"""Bounded, deterministic ranking of catalog-calculated meal combinations."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from decimal import Decimal
from itertools import product
from uuid import UUID
from time import monotonic

from pydantic import BaseModel, ConfigDict, Field

from app.planning.diagnostics import SearchDiagnostics, ScanStop
from app.planning.schemas import (
    DailyTarget,
    MealSlot,
    PlannedMeal,
    PreferenceReview,
    REQUIRED_MEAL_SLOTS,
)


SELECTION_POLICY_VERSION = "planning-selection.v11"


class PlanningSearchBudget(BaseModel):
    """Operator-controlled work budgets, independent of catalog size."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    batch_size: int = Field(default=64, ge=1, le=512)
    scan_per_slot: int = Field(default=2048, ge=1, le=100000)
    options_per_slot: int = Field(default=12, ge=1, le=64)
    max_combinations: int = Field(default=1728, ge=1, le=262144)
    scan_seconds_per_slot: float = Field(default=3, gt=0, le=30, allow_inf_nan=False)
    combination_seconds: float = Field(default=2, gt=0, le=30, allow_inf_nan=False)


class MealSelectionPolicy(BaseModel):
    """Soft ranking preferences, never substitutes for nutrition/exclusion validation."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    breakfast_weight: Decimal = Field(default=Decimal("25"), gt=0, le=1000)
    lunch_weight: Decimal = Field(default=Decimal("40"), gt=0, le=1000)
    dinner_weight: Decimal = Field(default=Decimal("35"), gt=0, le=1000)
    diversity_slots: int = Field(default=4, ge=0, le=64)
    diversity_weight: Decimal = Field(default=Decimal("0.05"), ge=0, le=1)
    flavour_diversity_weight: Decimal = Field(default=Decimal("0.25"), ge=0, le=1)

    bundle_enabled: bool = True
    bundle_options_per_role: int = Field(default=4, ge=1, le=8)
    bundle_max_combinations: int = Field(default=64, ge=1, le=512)
    bundle_seconds: float = Field(default=0.5, gt=0, le=5, allow_inf_nan=False)
    bundle_staple_weight: Decimal = Field(default=Decimal(45), gt=0, le=1000)
    bundle_protein_weight: Decimal = Field(default=Decimal(35), gt=0, le=1000)
    bundle_vegetable_weight: Decimal = Field(default=Decimal(20), gt=0, le=1000)

    portion_adjustment_enabled: bool = True
    portion_min_multiplier: Decimal = Field(default=Decimal("0.75"), ge=Decimal("0.5"), le=1)
    portion_max_multiplier: Decimal = Field(default=Decimal("1.25"), ge=1, le=Decimal("1.5"))
    max_target_deviation: Decimal = Field(default=Decimal("0.10"), ge=0, le=Decimal("0.25"))

    def weight(self, slot: MealSlot) -> Decimal:
        return getattr(self, f"{slot.value}_weight")


@dataclass(frozen=True)
class SelectionCandidate:
    """Transient catalog evidence; never added to public cards or graph checkpoints."""

    meal: PlannedMeal
    food_ids: frozenset[UUID] = frozenset()

    @property
    def identity(self) -> tuple[UUID, Decimal, tuple[Decimal, ...]]:
        # Equal total grams can hide different component amounts and nutrition.
        return self.meal.recipe_id, self.meal.portion_grams, tuple(item.portion_grams for item in self.meal.items)

    @property
    def methods(self) -> frozenset[str]:
        return frozenset(normalized_label(tag) for tag in self.meal.method_tags if normalized_label(tag))

    @property
    def flavours(self) -> frozenset[str]:
        return frozenset(normalized_label(tag) for tag in self.meal.flavour_tags if normalized_label(tag))

    @property
    def signature(self) -> tuple:
        return tuple(sorted(self.food_ids)), tuple(sorted(self.methods))


def _similarity(
    left: SelectionCandidate, right: SelectionCandidate, *,
    flavour_weight: Decimal = Decimal(0), preferred_flavours: frozenset[str] = frozenset(),
) -> Decimal:
    def overlap(a: frozenset, b: frozenset) -> Decimal:
        return Decimal(len(a & b)) / len(a | b) if a and b else Decimal(0)

    # Missing composition contributes no invented ingredient evidence. Known
    # methods can still diversify managed dishes that lack ingredient lists.
    flavour_overlap = Decimal(0)
    if flavour_weight:
        # Unknown labels provide no evidence of novelty; do not reward missing data.
        # Deliberately repeated user favourites are exempt from taste penalties.
        flavour_overlap = (
            overlap(left.flavours - preferred_flavours, right.flavours - preferred_flavours)
            if left.flavours and right.flavours else Decimal(1)
        )
    return (overlap(left.food_ids, right.food_ids) + Decimal("0.25") * overlap(left.methods, right.methods)
            + flavour_weight * flavour_overlap)


class _Shortlist:
    """Keep at most K nutritional leaders plus K distinct catalog-evidence leaders."""

    def __init__(
        self, capacity: int, reserve: int, *, flavour_weight: Decimal = Decimal(0),
        preferred_flavours: frozenset[str] = frozenset(),
    ) -> None:
        self.flavour_weight = flavour_weight
        self.preferred_flavours = preferred_flavours
        self.capacity = capacity
        self.reserve = min(reserve, capacity - 1)
        self.primary: list[tuple[tuple, SelectionCandidate]] = []
        self.groups: dict[tuple, tuple[tuple, SelectionCandidate]] = {}

    def add(self, candidate: SelectionCandidate, key: tuple) -> None:
        if any(item.identity == candidate.identity for _, item in self.primary):
            return
        self.primary.append((key, candidate))
        self.primary.sort(key=lambda entry: entry[0])
        del self.primary[self.capacity:]
        if self.reserve:
            signature = candidate.signature
            if self.flavour_weight:
                signature = (*signature, tuple(sorted(candidate.flavours - self.preferred_flavours)))
            previous = self.groups.get(signature)
            if previous is None or key < previous[0]:
                self.groups[signature] = (key, candidate)
            if len(self.groups) > self.capacity:
                del self.groups[max(self.groups, key=lambda group: self.groups[group][0])]

    def finish(self) -> tuple[SelectionCandidate, ...]:
        chosen = self.primary[:self.capacity - self.reserve]
        remaining = {item.identity: (key, item) for key, item in (*self.primary, *self.groups.values())}
        for _, item in chosen:
            remaining.pop(item.identity, None)
        while remaining and len(chosen) < self.capacity:
            entry = min(remaining.values(), key=lambda entry: (
                -len(entry[1].flavours & self.preferred_flavours) if self.flavour_weight else 0,
                sum((_similarity(entry[1], item, flavour_weight=self.flavour_weight,
                                 preferred_flavours=self.preferred_flavours) for _, item in chosen), Decimal(0)),
                entry[0],
            ))
            chosen.append(entry)
            del remaining[entry[1].identity]
        return tuple(item for _, item in sorted(chosen, key=lambda entry: entry[0]))


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
    options: Iterable[PlannedMeal | SelectionCandidate],
    target: DailyTarget | None,
    preferences: PreferenceReview,
    recent_recipe_ids: tuple[UUID, ...],
    fixed_meals: tuple[PlannedMeal, ...],
    validation_rank: Callable[[tuple[PlannedMeal, ...]], int],
    budget: PlanningSearchBudget | None = None,
    policy: MealSelectionPolicy | None = None,
    clock: Callable[[], float] = monotonic,
    diagnostics: SearchDiagnostics | None = None,
) -> tuple[PlannedMeal, ...]:
    """Stream a bounded shortlist, then search within count and cooperative time limits.

    Shortlisting is a bounded heuristic, not a claim of globally optimal nutrition.
    A previously used recipe remains eligible when it is the only valid solution.
    """

    diagnostics = diagnostics or SearchDiagnostics()
    budget = budget or PlanningSearchBudget()
    policy = policy or MealSelectionPolicy()
    fixed = {meal.slot: meal for meal in fixed_meals}
    fixed_ids = {identity for meal in fixed_meals for identity in meal.source_recipe_ids}
    recent = set(recent_recipe_ids)
    variable_slots = tuple(slot for slot in REQUIRED_MEAL_SLOTS if slot not in fixed)
    remaining_weight = sum((policy.weight(slot) for slot in variable_slots), Decimal(0))
    centers = {} if target is None else {metric: (getattr(target, metric).lower + getattr(target, metric).upper) / 2 for metric in _METRICS}
    residual = {metric: max(Decimal(0), center - sum((getattr(meal.nutrients, metric) for meal in fixed_meals), Decimal(0))) for metric, center in centers.items()}

    def allocation_distance(meal: PlannedMeal) -> Decimal:
        if not centers or not remaining_weight or meal.slot not in variable_slots:
            return Decimal(0)
        share = policy.weight(meal.slot) / remaining_weight
        return sum((abs(getattr(meal.nutrients, metric) - residual[metric] * share) / max(center, Decimal(1)) for metric, center in centers.items()), Decimal(0))

    def shortlist_key(meal: PlannedMeal) -> tuple:
        return (
            allocation_distance(meal),
            -preference_matches(meal, preferences),
            bool(set(meal.source_recipe_ids) & recent),
            str(meal.recipe_id),
            meal.portion_grams,
            tuple(item.portion_grams for item in meal.items),
        )

    preferred_flavours = frozenset(normalized_label(value) for value in preferences.taste_preferences if normalized_label(value))
    shortlists = {slot: _Shortlist(budget.options_per_slot, policy.diversity_slots,
                                 flavour_weight=policy.flavour_diversity_weight,
                                 preferred_flavours=preferred_flavours) for slot in variable_slots}
    for option in options:
        candidate = option if isinstance(option, SelectionCandidate) else SelectionCandidate(option)
        meal = candidate.meal
        if meal.slot in shortlists and not (set(meal.source_recipe_ids) & fixed_ids):
            shortlists[meal.slot].add(candidate, shortlist_key(meal))
    finalized = {slot: shortlist.finish() for slot, shortlist in shortlists.items()}
    # Record all slots before returning for an empty one, or a missing breakfast
    # would incorrectly make the failure message claim lunch/dinner are missing too.
    for slot, pool in finalized.items():
        diagnostics.slots[slot].shortlisted = len(pool)
    pools = []
    for slot in REQUIRED_MEAL_SLOTS:
        pool = (SelectionCandidate(fixed[slot]),) if slot in fixed else finalized[slot]
        if not pool:
            return ()
        pools.append(pool)

    extra_fixed = tuple(
        meal for meal in fixed_meals if meal.slot not in REQUIRED_MEAL_SLOTS
    )

    def score(candidates: tuple[SelectionCandidate, ...], meals: tuple[PlannedMeal, ...]) -> tuple:
        outside, midpoint = (
            (Decimal(0), Decimal(0)) if target is None else _distance(meals, target)
        )
        return (
            validation_rank(meals) if target is not None else 0,
            outside,
            -sum(preference_matches(meal, preferences) for meal in meals),
            sum(bool(set(meal.source_recipe_ids) & recent) for meal in meals),
            -sum(bool(meal.items) for meal in meals),
            midpoint + sum((allocation_distance(meal) for meal in meals), Decimal(0))
            + policy.diversity_weight * sum((_similarity(left, right, flavour_weight=policy.flavour_diversity_weight, preferred_flavours=preferred_flavours) for index, left in enumerate(candidates) for right in candidates[index + 1:]), Decimal(0)),
            tuple((str(meal.recipe_id), meal.portion_grams, tuple(item.portion_grams for item in meal.items)) for meal in meals),
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
        meals = (*(candidate.meal for candidate in combination), *extra_fixed)
        sources = [identity for meal in meals for identity in meal.source_recipe_ids]
        if len(set(sources)) != len(sources):
            diagnostics.duplicate_combinations += 1
            continue
        rank = score(combination, meals)
        if best_score is None or rank < best_score:
            best, best_score = meals, rank
    else:
        diagnostics.combination_stop = ScanStop.EXHAUSTED
    diagnostics.combination_elapsed_ms = max(0, int((clock() - started) * 1000))
    return best
