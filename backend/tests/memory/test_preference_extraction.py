"""Scope and classification regressions for deterministic memory extraction."""

import pytest

from app.memory.preferences import extract_explicit_preferences, summarize_memory_preferences


@pytest.mark.parametrize(("statement", "expected"), [
    ("不吃辣 饮食清淡", [("avoidance", "不吃辣", "long_term"), ("stable_preference", "清淡", "long_term")]),
    ("我不吃辣，而且饮食清淡", [("avoidance", "不吃辣", "long_term"), ("stable_preference", "清淡", "long_term")]),
    ("今天不想吃辣，饮食清淡", [("avoidance", "不吃辣", "current_plan"), ("stable_preference", "清淡", "current_plan")]),
    ("我今天不吃辣。我喜欢清淡", [("avoidance", "不吃辣", "current_plan"), ("stable_preference", "清淡", "current_plan")]),
    ("今天午餐换清淡一些，我不吃辣", [("avoidance", "不吃辣", "current_plan")]),
    ("今天不吃辣，我长期偏好少油", [("avoidance", "不吃辣", "current_plan"), ("stable_preference", "少油", "long_term")]),
    ("我不想 吃辣", [("avoidance", "不吃辣", "current_plan")]),
    ("我的目标是维持体重，我喜欢番茄", [("goal", "维持体重", "long_term"), ("stable_preference", "番茄", "long_term")]),
    ("我不吃辣，不吃辣", [("avoidance", "不吃辣", "long_term")]),
    ("今天 不吃 辣", [("avoidance", "不吃辣", "current_plan")]),
])
def test_compound_preferences_and_temporal_scope(statement, expected):
    assert [(p.category, p.canonical_text, p.scope) for p in extract_explicit_preferences(statement)] == expected


@pytest.mark.parametrize("statement", [
    "图片里看起来没有辣椒", "朋友不吃辣", "我朋友不吃辣", "我不吃辣吗",
    "如果我不吃辣，饮食清淡", "我以前不吃辣", "我不再喜欢清淡",
    "医生说：我不吃辣", "例如：我不吃辣", '他说“我不吃辣”',
    "别记住这句话，我不吃辣", "我不吃辣，请不要保存这条记忆", "我不吃辣，别放进长期记忆", "我不吃辣的人做的饭", "我不吃辣但是喜欢火锅",
    "我不吃辣 饮食清淡" * 1000,
])
def test_ambiguous_observed_or_over_budget_text_is_not_saved(statement):
    assert extract_explicit_preferences(statement) == []


def test_legacy_projection_splits_known_clauses_and_preserves_unknown_restrictions():
    summary = summarize_memory_preferences([
        ("avoidance", "不吃辣 饮食清淡"),
        ("avoidance", "花生、虾"),
        ("avoidance", "今天不吃牛肉，饮食少油"),
        ("stable_preference", "清淡"),
        ("goal", "减重"),
    ])
    assert summary.exclusions == ("不吃辣", "花生、虾")
    assert summary.taste_preferences == ("清淡",)
