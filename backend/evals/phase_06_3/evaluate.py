"""Strict, offline loader for the frozen Phase 06.3 retrieval cases."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


CASE_SCHEMA_VERSION = "phase063-case.v1"
CASE_FIELDS = (
    "schema_version",
    "case_id",
    "sequence",
    "kind",
    "query",
    "fixture_snapshot",
    "expected",
    "auto_pass_allowed",
    "catalog_version",
    "retrieval_version",
    "embedding_version",
    "parent_hash",
    "case_hash",
)
EXPECTED_FIELDS = (
    "action",
    "match_channel",
    "target_food_ids",
    "excluded_food_ids",
    "candidate_limit",
    "execution_mode",
)
REQUIRED_CASE_KINDS = frozenset({"exact", "non_exact", "ambiguity", "eligibility", "failure_determinism"})
_FORBIDDEN_FIELD_PARTS = frozenset({
    "email", "identity", "user", "meal", "body", "health", "image", "base64",
    "prompt", "provider", "response", "vector", "embedding_data", "token", "secret",
})
_LOCKED_NON_EXACT_TARGETS = {
    "西红柿炒鸡蛋": "food:tomato-egg-v1",
    "风干牛肉": "food:beef-jerky-v1",
    "四川烤鱼": "food:grilled-fish-v1",
    "定西土豆粉": "food:potato-noodles-v1",
    "包子": "food:pan-fried-bun-v1",
}


class EvaluationContractError(ValueError):
    """Stable CI-safe rejection for untrusted frozen evidence."""


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _load_rows(dataset: Path) -> list[dict[str, Any]]:
    try:
        rows = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line]
    except (OSError, json.JSONDecodeError) as error:
        raise EvaluationContractError("frozen retrieval dataset is unreadable") from error
    if not rows or not all(isinstance(row, dict) for row in rows):
        raise EvaluationContractError("frozen retrieval dataset must contain object rows")
    return rows


def _validate_expected(expected: object) -> dict[str, Any]:
    if not isinstance(expected, dict) or tuple(expected) != EXPECTED_FIELDS:
        raise EvaluationContractError("case expectation fields do not match the frozen contract")
    if expected["action"] not in {"PASS", "ASK"} or expected["match_channel"] not in {"exact", "hybrid", "text_fallback", "none"}:
        raise EvaluationContractError("case action or channel is invalid")
    if not all(isinstance(expected[key], list) and all(isinstance(item, str) and item.startswith("food:") for item in expected[key]) for key in ("target_food_ids", "excluded_food_ids")):
        raise EvaluationContractError("case food identifiers are invalid")
    if not isinstance(expected["candidate_limit"], int) or not 0 <= expected["candidate_limit"] <= 3 or not isinstance(expected["execution_mode"], str):
        raise EvaluationContractError("case candidate contract is invalid")
    return expected


def validate_dataset(dataset: Path) -> list[dict[str, Any]]:
    """Load only evidence that has the exact frozen schema, ordering and chain."""

    rows, parent_hash = _load_rows(dataset), None
    for sequence, row in enumerate(rows, start=1):
        if any(part in key.lower() for key in row for part in _FORBIDDEN_FIELD_PARTS if key not in {"embedding_version"}):
            raise EvaluationContractError("case contains a forbidden sensitive or privacy field")
        if tuple(row) != CASE_FIELDS:
            raise EvaluationContractError("case fields or field order do not match the frozen contract")
        if row["schema_version"] != CASE_SCHEMA_VERSION or row["case_id"] != f"phase063-{sequence:03d}" or row["sequence"] != sequence:
            raise EvaluationContractError("case version, identifier, or sequence is invalid")
        if not isinstance(row["query"], str) or not row["query"] or not isinstance(row["fixture_snapshot"], str) or not row["fixture_snapshot"].startswith("synthetic:"):
            raise EvaluationContractError("case query or synthetic snapshot is invalid")
        if not all(isinstance(row[key], str) and row[key] for key in ("catalog_version", "retrieval_version", "embedding_version")):
            raise EvaluationContractError("case version declarations are invalid")
        expected = _validate_expected(row["expected"])
        if row["parent_hash"] != parent_hash:
            raise EvaluationContractError("case parent hash chain is invalid")
        if not isinstance(row["case_hash"], str) or row["case_hash"] != _hash({key: value for key, value in row.items() if key != "case_hash"}):
            raise EvaluationContractError("case hash does not match canonical content")
        if not isinstance(row["auto_pass_allowed"], bool) or (expected["action"] == "PASS") != row["auto_pass_allowed"]:
            raise EvaluationContractError("case auto-pass contract is invalid")
        if row["kind"] == "non_exact" and (expected["action"] != "ASK" or row["auto_pass_allowed"] or not expected["target_food_ids"]):
            raise EvaluationContractError("non-exact cases must require confirmation without an exact bypass")
        parent_hash = row["case_hash"]

    if len(rows) < 24 or REQUIRED_CASE_KINDS - {row["kind"] for row in rows}:
        raise EvaluationContractError("frozen dataset is missing required category coverage")
    for query, target in _LOCKED_NON_EXACT_TARGETS.items():
        matching = [row for row in rows if row["query"] == query and row["kind"] == "non_exact"]
        if len(matching) != 1 or target not in matching[0]["expected"]["target_food_ids"]:
            raise EvaluationContractError("frozen dataset is missing a locked Top-3 mapping")
    if not any(row["query"] == "米饭" and row["expected"]["action"] == "PASS" and row["expected"]["target_food_ids"] == ["food:rice-v1"] for row in rows):
        raise EvaluationContractError("frozen dataset is missing the rice exact-pass mapping")
    return rows
