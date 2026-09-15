"""Conservative, deterministic preference extraction; no model or persistence access."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


PREFERENCE_RULE_VERSION = "explicit-preferences.v2"
MAX_STATEMENT_LENGTH = 8000
MAX_PREFERENCES = 12


class ExplicitPreference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    category: Literal["goal", "avoidance", "stable_preference"]
    canonical_text: str = Field(min_length=1, max_length=1000)
    scope: Literal["long_term", "current_plan"]


class PreferenceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    exclusions: tuple[str, ...] = ()
    taste_preferences: tuple[str, ...] = ()


_TEMPORARY = re.compile(r"今天|今日|明天|今晚|这次|本次|这顿|本顿|这餐|本餐|这周|本周|最近|暂时|这几天|现在|不想吃|早餐|午餐|晚餐|早饭|午饭|晚饭")
_LONG_TERM = re.compile(r"^(?:我)?(?:一直|长期|平时|通常|从来)")
_PREFIX = re.compile(r"^(?:(?:我)|(?:今天|今日|明天|今晚|这次|本次|这顿|本顿|这餐|本餐|这周|本周|最近|暂时|这几天|现在|早餐|午餐|晚餐|早饭|午饭|晚饭)|(?:一直|长期|平时|通常|从来|都))+")
# Only split whitespace/conjunctions before a recognizable statement, never inside a food name.
_CLAUSES = re.compile(r"[，,。！!；;\n]+|(?:\s+|并且|而且|且)(?=(?:我|不吃|不想吃|饮食|口味|今天|本次|暂时|长期|平时))")
_UNSAFE = re.compile(r"[?？\"'“”‘’=]|(?:不要|别|不用|不必|无需).*(?:保存|存|记|长期)|不保存|如果|假如|可能|也许|以前|过去|曾经|不再|不是|取消|不要记|别记|例如|比如|说|建议|能否|是否|吗|呢|怎么办|但是|不过")


def preference_clauses(statement: str) -> list[tuple[str, Literal["long_term", "current_plan"]]]:
    """Temporal scope carries across a sentence unless explicitly reset to a stable habit."""
    if len(statement) > MAX_STATEMENT_LENGTH or _UNSAFE.search(statement):
        return []
    scope: Literal["long_term", "current_plan"] = "long_term"
    clauses = []
    for raw in _CLAUSES.split(statement):
        clause = " ".join(raw.split()).strip()
        if not clause:
            continue
        if _TEMPORARY.search(clause.replace(" ", "")):
            scope = "current_plan"
        elif _LONG_TERM.match(clause.replace(" ", "")):
            scope = "long_term"
        clauses.append((clause, scope))
    return clauses


def _parse_clause(clause: str, scope: Literal["long_term", "current_plan"]) -> ExplicitPreference | None:
    compact = clause.replace(" ", "")
    body = _PREFIX.sub("", compact)
    avoidance = re.fullmatch(r"(?:不想吃|不吃)([^，。；!?？]{1,80})", body)
    if avoidance:
        item = avoidance.group(1)
        # Clauses containing another intent are ambiguous, not a canonical food restriction.
        if re.search(r"想|喜欢|偏好|饮食|口味|目标|换|记住|说|的人|的朋友|的时候|的话", item):
            return None
        return ExplicitPreference(category="avoidance", canonical_text=f"不吃{item}", scope=scope)
    goal = re.fullmatch(r"(?:的)?目标(?:是|为)(减脂|减重|增肌|增重|维持体重|保持体重)", body)
    if goal:
        return ExplicitPreference(category="goal", canonical_text=goal.group(1), scope=scope)
    taste = re.fullmatch(r"(?:(?:饮食|口味)(?:偏好|偏|喜欢)?|喜欢|偏好)(清淡|少油|少盐|低盐|微辣|偏辣|重口味|酸甜|甜口|咸口)", body)
    if taste:
        return ExplicitPreference(category="stable_preference", canonical_text=taste.group(1), scope=scope)
    preference = re.fullmatch(r"(?:喜欢|偏好)([\u4e00-\u9fffA-Za-z]{1,40})", body)
    if preference and not re.search(r"不|想|换|记住|说|的人|的朋友|的时候|的话", preference.group(1)):
        return ExplicitPreference(category="stable_preference", canonical_text=preference.group(1), scope=scope)
    return None


def extract_explicit_preferences(statement: str) -> list[ExplicitPreference]:
    """Unknown/ambiguous wording is not guessed into a long-term memory."""
    result: list[ExplicitPreference] = []
    for clause, scope in preference_clauses(statement):
        preference = _parse_clause(clause, scope)
        if preference is not None and preference not in result:
            result.append(preference)
        if len(result) == MAX_PREFERENCES:
            break
    return result


def summarize_memory_preferences(memories: list[tuple[str, str]]) -> PreferenceSummary:
    """Read projection only: split legacy compound text without rewriting its ledger/replica.

    Unrecognized stored restrictions remain visible for confirmation. Dropping them could
    silently weaken an exclusion; temporary clauses, however, must not leak to future plans.
    """
    exclusions: list[str] = []
    tastes: list[str] = []
    for category, text in memories:
        if category not in {"avoidance", "stable_preference"}:
            continue
        clauses = preference_clauses(text)
        if not clauses:
            clauses = [(text, "current_plan" if _TEMPORARY.search(text) else "long_term")]
        for clause, scope in clauses:
            if scope == "current_plan":
                continue
            parsed = _parse_clause(clause, scope)
            resolved_category = parsed.category if parsed else category
            if resolved_category == "goal":
                continue
            value = parsed.canonical_text if parsed else clause
            destination = exclusions if resolved_category == "avoidance" else tastes
            if value not in destination:
                destination.append(value)
    return PreferenceSummary(exclusions=tuple(exclusions), taste_preferences=tuple(tastes))
