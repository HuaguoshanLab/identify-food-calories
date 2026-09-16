"""Bounded meal bundles made only from explicitly classified catalog evidence."""

from collections.abc import Callable, Iterator
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


class BundlePool:
    """Hold at most K distinct foods per role, then inspect at most K³ bundles.

    Role energy weights are search hints, not nutrition recommendations. Portions
    remain the explicitly authored component portions; all daily checks still apply.
    """

    def __init__(
        self, *, slot: MealSlot, energy: Decimal | None, policy: MealSelectionPolicy,
        preferences: PreferenceReview, recent: tuple[UUID, ...],
        stats: SlotDiagnostics, clock: Callable[[], float],
    ) -> None:
        self.slot, self.energy, self.policy = slot, energy, policy
        self.preferences, self.recent = preferences, set(recent)
        self.stats, self.clock = stats, clock
        self.pools: dict[str, list[tuple[tuple, PlannedMealItem, PlannedMeal]]] = {role: [] for role in BUNDLE_ROLES}
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
        item = PlannedMealItem(
            recipe_id=candidate.id, recipe_revision=candidate.revision,
            nutrition_item_id=candidate.nutrition_item_id, catalog_version=candidate.catalog_version,
            meal_role=role, display_name=meal.display_name, portion_grams=meal.portion_grams,
            portion_description=meal.portion_description, method_tags=meal.method_tags,
            flavour_tags=meal.flavour_tags, nutrients=meal.nutrients,
        )
        # Duplicate catalog foods must not consume all the slots in a role pool.
        pool = self.pools[role]
        existing = next((entry for entry in pool if entry[1].nutrition_item_id == item.nutrition_item_id), None)
        if existing is not None:
            if existing[0] <= key:
                return
            pool.remove(existing)
        pool.append((key, item, meal))
        pool.sort(key=lambda entry: entry[0])
        del pool[self.policy.bundle_options_per_role:]
        self.stats.components += 1

    def finish(self, *, excluded: tuple[UUID, ...]) -> Iterator[SelectionCandidate]:
        deadline = self.clock() + self.policy.bundle_seconds
        for index, entries in enumerate(product(*(self.pools[role] for role in BUNDLE_ROLES))):
            if index >= self.policy.bundle_max_combinations:
                self.stats.bundle_stop = ScanStop.COUNT
                return
            if self.clock() >= deadline:
                self.stats.bundle_stop = ScanStop.TIME
                return
            self.stats.bundle_attempts += 1
            items = tuple(entry[1] for entry in entries)
            if len({item.nutrition_item_id for item in items}) != len(items):
                continue
            # An aggregate ID names the combination only. Archive provenance uses
            # actual component IDs and the revisions observed during calculation.
            identity = uuid5(NAMESPACE_URL, "planning-bundle.v1:" + self.slot.value + ":" + ":".join(
                f"{item.recipe_id}@{item.recipe_revision}" for item in items
            ))
            if identity in excluded or any(item.recipe_id in excluded for item in items):
                continue
            def labels(field: str) -> tuple[str, ...]:
                return tuple(dict.fromkeys(value for entry in entries for value in getattr(entry[2], field)))
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
            self.stats.bundles += 1
            yield SelectionCandidate(meal, frozenset(item.nutrition_item_id for item in items))
        self.stats.bundle_stop = ScanStop.EXHAUSTED
