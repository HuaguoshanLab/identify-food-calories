"""Parse user-supplied meal weights; never infer portions or nutrition values."""

import re
from decimal import Decimal, localcontext

WEIGHT_INPUT_VERSION = "meal-weight-input.v1"
MAX_MEAL_WEIGHT_GRAMS = Decimal("2000")
_WEIGHT = re.compile(r"([0-9]+(?:\.[0-9]+)?|\.[0-9]+)\s*(g|克|公克|kg|千克|公斤|斤|市斤|两|市两)?", re.IGNORECASE)
_GRAMS_PER_UNIT = {
    "": Decimal("1"), "g": Decimal("1"), "克": Decimal("1"), "公克": Decimal("1"),
    "kg": Decimal("1000"), "千克": Decimal("1000"), "公斤": Decimal("1000"),
    "斤": Decimal("500"), "市斤": Decimal("500"), "两": Decimal("50"), "市两": Decimal("50"),
}


class InvalidWeightInput(ValueError):
    """Contains only a fixed user-safe explanation, never echoes raw input."""


def parse_weight_grams(value: object) -> Decimal:
    """Return grams for one complete weight literal; 斤/两 mean mainland 市斤/市两.

    Full matching is essential: extracting digits from 100kg or 100ml would silently
    change their meaning. Bounds apply after conversion, not to the numeric prefix.
    """
    message = "请输入有效重量，例如 100g、0.1kg 或 2两；仅支持克、千克/公斤、市斤、市两。"
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise InvalidWeightInput(message)
    raw = str(value).strip()
    match = _WEIGHT.fullmatch(raw) if len(raw) <= 80 else None
    if match is None:
        raise InvalidWeightInput(message)
    # Enough precision for every accepted literal, independent of the caller's context.
    with localcontext() as context:
        context.prec = 100
        grams = Decimal(match[1]) * _GRAMS_PER_UNIT[(match[2] or "").lower()]
    if not Decimal("0") < grams <= MAX_MEAL_WEIGHT_GRAMS:
        raise InvalidWeightInput("换算后的单项重量必须大于 0 且不超过 2000 克，请更正后提交。")
    return grams
