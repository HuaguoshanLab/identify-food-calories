"""Bounded meal bundles made only from explicitly classified catalog evidence."""

from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from decimal import Decimal
from itertools import product
from uuid import NAMESPACE_URL, UUID, uuid5

from app.planning.diagnostics import SlotDiagnostics, ScanStop
from app.planning.schemas import (
    ManagedRecipeCandidate, MealSlot, PlannedMeal, PlannedMealItem,
    PlanningNutritionValues, PreferenceReview,
)
from app.planning.selection import MealSelectionPolicy, SelectionCandidate, preference_matches


BUNDLE_ROLES = ("staple", "protein", "vegetable")
BUNDLE_SLOTS = (MealSlot.LUNCH, MealSlot.DINNER)


@dataclass(frozen=True)
class _Component:
    key: tuple
    candidate: ManagedRecipeCandidate
    item: PlannedMealItem
    meal: PlannedMeal


AdaptComponent = Callable[[ManagedRecipeCandidate, PlannedMeal, Decimal], PlannedMeal | None]


class BundlePool:
    """Hold K foods per role and try original/adapted portions within one budget.

    Role energy weights are search hints, not nutrition recommendations. Adaptation
    is delegated to the service so every new portion is calculated by nutrition.
    """

    def __init__(
        self, *, slot: MealSlot, energy: Decimal | None, policy: MealSelectionPolicy,
        preferences: PreferenceReview, recent: tuple[UUID, ...],
        stats: SlotDiagnostics, clock: Callable[[], float],
    ) -> None:
        self.slot, self.energy, self.policy = slot, energy, policy
        self.preferences, self.recent = preferences, set(recent)
        self.stats, self.clock = stats, clock
        self.pools: dict[str, list[_Component]] = {role: [] for role in BUNDLE_ROLES}
        self.weight_sum = sum(getattr(policy, f"bundle_{role}_weight") for role in BUNDLE_ROLES)

    def add(self, candidate: ManagedRecipeCandidate, meal: PlannedMeal) -> None:
        role = candidate.meal_role
        if role not in self.pools:
            return
        desired = self.energy * getattr(self.policy, f"bundle_{role}_weight") / self.weight_sum if self.energy is not None else None
        key = (
            abs(meal.nutrients.energy_kcal - desired) if desired is not None else Decimal(0),
            -preference_matches(meal, self.preferences), candidate.id in self.recent, str(candidate.id),
        )
        item = self._item(candidate, meal)
        # Duplicate catalog foods must not consume all the slots in a role pool.
        pool = self.pools[role]
        existing = next((entry for entry in pool if entry.item.nutrition_item_id == item.nutrition_item_id), None)
        if existing is not None:
            if existing.key <= key:
                return
            pool.remove(existing)
        pool.append(_Component(key, candidate, item, meal))
        pool.sort(key=lambda entry: entry.key)
        del pool[self.policy.bundle_options_per_role:]
        self.stats.components += 1

    @staticmethod
    def _item(candidate: ManagedRecipeCandidate, meal: PlannedMeal) -> PlannedMealItem:
        role = candidate.meal_role
        assert role == "staple" or role == "protein" or role == "vegetable"
        return PlannedMealItem(
            recipe_id=candidate.id, recipe_revision=candidate.revision,
            nutrition_item_id=candidate.nutrition_item_id, catalog_version=candidate.catalog_version,
            meal_role=role, display_name=meal.display_name, portion_grams=meal.portion_grams,
            portion_description=meal.portion_description, method_tags=meal.method_tags,
            flavour_tags=meal.flavour_tags, nutrients=meal.nutrients,
        )

    def finish(self, *, excluded: tuple[UUID, ...], adapt: AdaptComponent | None = None) -> Iterator[SelectionCandidate]:
        deadline = self.clock() + self.policy.bundle_seconds
        self.stats.bundle_stop = None
        attempts = 0
        cache: dict[UUID, _Component | None] = {}
        can_adapt = adapt is not None and self.policy.portion_adjustment_enabled and self.energy is not None
        for original in product(*(self.pools[role] for role in BUNDLE_ROLES)):
            items = tuple(entry.item for entry in original)
            # An aggregate ID names the combination only. Archive provenance uses
            # actual component IDs and the revisions observed during calculation.
            identity = uuid5(NAMESPACE_URL, "planning-bundle.v1:" + self.slot.value + ":" + ":".join(
                f"{item.recipe_id}@{item.recipe_revision}" for item in items
            ))
            for adjusted in ((False, True) if can_adapt else (False,)):
                if attempts >= self.policy.bundle_max_combinations:
                    self.stats.bundle_stop = ScanStop.COUNT
                    return
                if self.clock() >= deadline:
                    self.stats.bundle_stop = ScanStop.TIME
                    return
                self.stats.bundle_attempts += 1
                attempts += 1
                if len({item.nutrition_item_id for item in items}) != len(items) or identity in excluded or any(item.recipe_id in excluded for item in items):
                    break
                entries = original
                if adjusted:
                    assert adapt is not None
                    adapted = self._adjust(original, adapt, cache, deadline)
                    if self.stats.bundle_stop is ScanStop.TIME:
                        return
                    if adapted is None or all(a.item.portion_grams == b.item.portion_grams for a, b in zip(adapted, original, strict=True)):
                        continue
                    entries = adapted
                    self.stats.adapted_bundles += 1
                self.stats.bundles += 1
                yield self._bundle(entries, identity)
        self.stats.bundle_stop = ScanStop.EXHAUSTED

    def _adjust(self, entries: tuple[_Component, ...], adapt: AdaptComponent,
                cache: dict[UUID, _Component | None], deadline: float) -> tuple[_Component, ...] | None:
        assert self.energy is not None
        result = []
        for entry in entries:
            if self.clock() >= deadline:
                self.stats.bundle_stop = ScanStop.TIME
                return None
            identity = entry.candidate.id
            if identity not in cache:
                desired = self.energy * getattr(self.policy, f"bundle_{entry.item.meal_role}_weight") / self.weight_sum
                meal = adapt(entry.candidate, entry.meal, desired)
                cache[identity] = None if meal is None else replace(entry, item=self._item(entry.candidate, meal), meal=meal)
                if meal is not None and meal.portion_grams != entry.meal.portion_grams:
                    self.stats.adapted_components += 1
                # A synchronous nutrition call cannot be interrupted; never start
                # another call or emit an adjusted bundle after its deadline.
                if self.clock() >= deadline:
                    self.stats.bundle_stop = ScanStop.TIME
                    return None
            adjusted = cache[identity]
            if adjusted is None:
                return None
            result.append(adjusted)
        return tuple(result)

    def _bundle(self, entries: tuple[_Component, ...], identity: UUID) -> SelectionCandidate:
        items = tuple(entry.item for entry in entries)

        def labels(field: str) -> tuple[str, ...]:
            return tuple(dict.fromkeys(value for entry in entries for value in getattr(entry.meal, field)))

        meal = PlannedMeal(
            slot=self.slot, recipe_id=identity,
            display_name="午餐组合餐" if self.slot is MealSlot.LUNCH else "晚餐组合餐",
            portion_description="主食、蛋白质菜与蔬菜各一份",
            portion_grams=sum((item.portion_grams for item in items), Decimal(0)),
            method_tags=labels("method_tags"), flavour_tags=labels("flavour_tags"),
            matched_preference_summaries=labels("matched_preference_summaries"),
            matched_exclusion_summaries=labels("matched_exclusion_summaries"),
            nutrients=PlanningNutritionValues(**{
                metric: sum((getattr(item.nutrients, metric) for item in items), Decimal(0))
                for metric in PlanningNutritionValues.model_fields
            }), items=items,
        )
        return SelectionCandidate(meal, frozenset(item.nutrition_item_id for item in items))
