"""Failure classification and privacy contracts for bounded planning searches."""

import json
import logging
import uuid

import pytest

from app.planning.diagnostics import SearchDiagnostics, ScanStop
from app.planning.schemas import CompositionFailureReason, MealSlot, PlanValidationAction, PreferenceReview
from app.planning.selection import PlanningSearchBudget
from app.planning.service import PlanningService
from tests.planning.test_personalized_selection import setup_pool, target
from tests.planning.test_planning_service import RecipeNutritionPort


def summary(caplog):
    records = [record for record in caplog.records if record.message.startswith("planning_search ")]
    assert len(records) == 1
    return json.loads(records[0].message.split("metrics=", 1)[1])


@pytest.mark.parametrize("missing_slot", [MealSlot.BREAKFAST, MealSlot.DINNER])
def test_missing_slot_reports_which_meal_instead_of_loop_limit(caplog, missing_slot):
    caplog.set_level(logging.INFO, logger="app.planning.diagnostics")
    service, repo, small, _ = setup_pool()
    repo.candidates = [item for item in small if item.meal_slot is not missing_slot]
    result = service.compose_daily_meals(catalog_version=None, preferences=PreferenceReview(confirmed=True))
    assert result.failure_reason is CompositionFailureReason.MISSING_SLOT
    labels = {MealSlot.BREAKFAST: "早餐", MealSlot.LUNCH: "午餐", MealSlot.DINNER: "晚餐"}
    assert labels[missing_slot] in result.safe_message
    assert all(label not in result.safe_message for slot, label in labels.items() if slot is not missing_slot)
    stats = summary(caplog)
    assert stats["slots"][missing_slot.value]["stop"] == "exhausted"
    assert stats["slots"][missing_slot.value]["scanned"] == 0


def test_exclusions_are_counted_before_nutrition_and_user_text_is_not_logged(caplog):
    caplog.set_level(logging.INFO, logger="app.planning.diagnostics")
    service, repo, _, large = setup_pool()
    repo.candidates = large
    user_id = uuid.uuid4()
    preferences = PreferenceReview(confirmed=True, exclusions=("不吃香辣", "私人偏好正文"))
    result = service.compose_daily_meals(user_id=user_id, catalog_version=None, preferences=preferences)
    assert result.failure_reason is CompositionFailureReason.EXCLUSIONS
    stats = summary(caplog)
    for slot in stats["slots"].values():
        assert slot["excluded"] == 1
        assert slot["nutrition_calls"] == slot["eligible"] == 0
    for sensitive in [str(user_id), "私人偏好正文", "不吃香辣", *(item.display_name for item in large), *(str(item.id) for item in large)]:
        assert sensitive not in caplog.text


def test_unavailable_nutrition_is_distinct_from_user_exclusion(caplog):
    caplog.set_level(logging.INFO, logger="app.planning.diagnostics")
    service, _, _, _ = setup_pool()
    service._nutrition_port = RecipeNutritionPort([])
    result = service.compose_daily_meals(catalog_version=None, preferences=PreferenceReview(confirmed=True))
    assert result.failure_reason is CompositionFailureReason.NUTRITION_UNAVAILABLE
    stats = summary(caplog)
    assert all(slot["unavailable"] == 2 for slot in stats["slots"].values())


def test_count_budget_does_not_claim_that_all_recipes_were_excluded(caplog):
    caplog.set_level(logging.INFO, logger="app.planning.diagnostics")
    service, repo, small, large = setup_pool()
    repo.candidates = [large[index].model_copy(update={"id": uuid.UUID(int=index + 1)}) for index in range(3)] + small
    service._search_budget = PlanningSearchBudget(batch_size=1, scan_per_slot=1)
    result = service.compose_daily_meals(catalog_version=None, preferences=PreferenceReview(confirmed=True, exclusions=("辣",)))
    assert result.failure_reason is CompositionFailureReason.SEARCH_BUDGET
    assert "额度已用完" in result.safe_message
    assert all(slot["stop"] == "count_budget" for slot in summary(caplog)["slots"].values())


def test_success_records_bounded_search_and_validation_counts(caplog):
    caplog.set_level(logging.INFO, logger="app.planning.diagnostics")
    service, _, _, _ = setup_pool()
    result = service.compose_daily_meals(catalog_version=None, target=target("1800"), preferences=PreferenceReview(confirmed=True))
    assert result.action is PlanValidationAction.PASS
    assert result.failure_reason is None
    stats = summary(caplog)
    assert stats["combinations"] == 8
    assert stats["validation_pass"] + stats["validation_relax"] + stats["validation_rejected"] == 8
    assert stats["combination_stop"] == "exhausted"


def test_combination_budget_failure_is_distinct_from_incompatible_candidates():
    diagnostics = SearchDiagnostics()
    for slot in diagnostics.slots.values():
        slot.shortlisted = 1
    diagnostics.combination_stop = ScanStop.COUNT
    assert PlanningService._search_failure(diagnostics, ()).failure_reason is CompositionFailureReason.SEARCH_BUDGET
    diagnostics.combination_stop = ScanStop.EXHAUSTED
    assert PlanningService._search_failure(diagnostics, ()).failure_reason is CompositionFailureReason.NO_COMBINATION


def test_fixed_slots_do_not_appear_in_missing_slot_message():
    from tests.planning.test_planning_service import valid_daily_meals
    diagnostics = SearchDiagnostics()
    fixed = tuple(meal for meal in valid_daily_meals() if meal.slot is not MealSlot.LUNCH)
    result = PlanningService._search_failure(diagnostics, fixed)
    assert "午餐" in result.safe_message
    assert "早餐" not in result.safe_message and "晚餐" not in result.safe_message


def test_diagnostics_rejects_unapproved_fields():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        SearchDiagnostics(user_id=str(uuid.uuid4()))
