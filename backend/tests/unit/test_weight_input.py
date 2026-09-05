"""Deterministic user-weight grammar; no model or database required."""

from decimal import Decimal, localcontext
import asyncio
import json

import pytest

from app.agent.weight import InvalidWeightInput, parse_weight_grams


@pytest.mark.parametrize(("value", "expected"), [
    ("100", "100"), (100, "100"), ("100g", "100"), ("100 G", "100"),
    ("100 克", "100"), ("100公克", "100"), ("100.5g", "100.5"),
    (".5g", "0.5"), (" 0.1 KG ", "100"), ("0.1千克", "100"),
    ("0.1公斤", "100"), ("0.2斤", "100"), ("1市斤", "500"),
    ("2两", "100"), ("2市两", "100"), ("2kg", "2000"),
    ("4斤", "2000"), ("40两", "2000"), (Decimal("0.001"), "0.001"),
])
def test_weight_units(value: object, expected: str) -> None:
    assert parse_weight_grams(value) == Decimal(expected)


@pytest.mark.parametrize("value", [
    "100kg", "100斤", "2.001kg", "2001", "0", "-1", "-1斤", "", " ",
    "100mg", "1lb", "1oz", "100ml", "1台斤", "1港斤", "半碗", "适量",
    "100g垃圾", "100g 200g", "1,000g", "1e2", "NaN", "Infinity", "+100g",
    "100kgg", "100g/kg", "一斤", "１００g", "1" * 81, None, True, [], {},
])
def test_invalid_weight_is_never_truncated_or_guessed(value: object) -> None:
    with pytest.raises(InvalidWeightInput):
        parse_weight_grams(value)


def test_conversion_does_not_depend_on_ambient_decimal_precision() -> None:
    with localcontext() as context:
        context.prec = 2
        assert parse_weight_grams("0.123456kg") == Decimal("123.456")


@pytest.mark.parametrize("structured", [False, True])
@pytest.mark.parametrize("value", ["100g", "0.1kg", "0.2斤", "2两"])
def test_plain_and_json_answers_share_the_parser(monkeypatch, structured: bool, value: str) -> None:
    from app.agent.service import AgentService
    from app.agent.state import AgentNextAction, ClarificationQuestion
    from tests.unit.test_runtime_foundation import _initial_state

    state = _initial_state().model_copy(update={
        "next_action": AgentNextAction.ASK_USER,
        "clarification_questions": (ClarificationQuestion(item_id="item-1", field="grams", message="weight"),),
    })

    async def load(**_kwargs):
        return state

    monkeypatch.setattr(AgentService, "_load_checkpoint", staticmethod(load))
    # This path only reads the supplied checkpoint; a repository call would fail.
    service = AgentService(repository=object())
    text = json.dumps({"answers": {"item-1": {"grams": value}}}) if structured else value
    payload = asyncio.run(service.resume_payload_for_text(checkpointer=object(), thread_id=state.thread_id, text=text))
    assert Decimal(payload["answers"]["item-1"]["grams"]) == Decimal("100")
