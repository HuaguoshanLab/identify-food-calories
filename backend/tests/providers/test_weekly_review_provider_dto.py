"""Runtime DTO and Fake boundary contracts for weekly-review generation."""

from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest

from app.dashboard.weekly_review_graph import validate_weekly_review_semantics
from app.providers.reasoning.dto import ProviderUsageDTO, WeeklyReviewFactsDTO, WeeklyReviewOutputDTO, WeeklyReviewRequest, WeeklyReviewSuggestionDTO
from app.providers.reasoning.fake import FakeReasoningModelProvider


def _facts() -> dict[str, object]:
    return {"week_start": "2026-08-24", "week_end_exclusive": "2026-08-31", "week_kind": "completed", "coverage_days": 5, "meal_count": 11, "totals": {"energy_kcal": 7200, "protein_g": 310, "fat_g": 240, "carbohydrate_g": 910}, "allowed_patterns": ["food_variety"], "coverage_sufficient": True, "facts_version": "weekly-facts.v1"}


def test_weekly_request_has_only_deidentified_allowlisted_facts() -> None:
    request = WeeklyReviewRequest(facts=_facts(), prompt_version="weekly-review-prompt.v1", schema_version="weekly-review-schema.v1")
    assert request.facts.meal_count == 11
    with pytest.raises(ValueError):
        WeeklyReviewRequest.model_validate({**request.model_dump(), "facts": {**request.facts.model_dump(), "email": "x@example.invalid"}})


@pytest.mark.parametrize("text", ["Take 2000 kcal every day.", "This diagnoses a disease.", "You must skip meals.", "Here is my reasoning first."])
def test_weekly_output_rejects_numeric_medical_coercive_and_reasoning_text(text: str) -> None:
    with pytest.raises(ValueError):
        validate_weekly_review_semantics(WeeklyReviewOutputDTO(suggestions=[WeeklyReviewSuggestionDTO(category="food_variety", text=text)], disclaimer="仅基于已记录数据，供一般饮食参考，不构成医疗建议。"), WeeklyReviewFactsDTO.model_validate(_facts()))


def test_fake_discards_weekly_request_body_from_trace() -> None:
    provider = FakeReasoningModelProvider()
    provider.queue_weekly_review_result(WeeklyReviewOutputDTO(suggestions=[WeeklyReviewSuggestionDTO(category="food_variety", text="Consider including a wider range of food groups in recorded meals.")], disclaimer="仅基于已记录数据，供一般饮食参考，不构成医疗建议。"), usage=ProviderUsageDTO(prompt_tokens=12, completion_tokens=16, cost_usd=Decimal("0.001")))
    asyncio.run(provider.generate_weekly_review(WeeklyReviewRequest(facts=_facts())))
    assert len(provider.calls) == 1
    assert provider.calls[0].operation == "generate_weekly_review"
    assert not hasattr(provider.calls[0], "request")
