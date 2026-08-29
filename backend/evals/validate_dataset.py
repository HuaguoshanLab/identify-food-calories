"""Fail closed on malformed, semantically weak, or silently rewritten frozen cases."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "phase02-case.v1"
ALLOWED_CATEGORIES = {"happy", "missing_ambiguity", "validation_budget"}
HAPPY_TRACE = (
    "parse_input",
    "search_food_catalog",
    "calculate_nutrition",
    "validate_nutrition_result",
    "build_report",
)
HAPPY_EVENTS = (
    "input_understood",
    "catalog_queried",
    "nutrition_calculated",
    "nutrition_validated",
    "completed",
)
REQUIRED_REPORT_FIELDS = {"items", "total", "unaccounted_items", "warnings", "disclaimer"}
FORBIDDEN_HAPPY_ASSERTIONS = {
    "waiting_input",
    "missing_ambiguity",
    "validation_budget",
    "failed",
    "limit_reached",
    "provider_nutrition_value",
    "chain_of_thought",
}
TAG_CATEGORY = {
    "out_of_catalog": "missing_ambiguity",
    "negative_grams": "validation_budget",
    "tool_failure": "validation_budget",
}
SENSITIVE_KEY_PARTS = {"api_key", "password", "secret", "token", "chain_of_thought", "reasoning_content"}
SENSITIVE_VALUE_PATTERN = re.compile(
    r"(?:sk-[A-Za-z0-9]|bearer\s+[A-Za-z0-9]|-----BEGIN|\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b)",
    re.IGNORECASE,
)


class DatasetValidationError(ValueError):
    """A stable, non-sensitive failure suitable for CI output."""


def _canonical_hash(record: dict[str, Any]) -> str:
    payload = {key: value for key, value in record.items() if key != "case_hash"}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _parse_composition(value: str) -> dict[str, int]:
    expected: dict[str, int] = {}
    for item in value.split(","):
        category, separator, count = item.partition("=")
        if not separator or category not in ALLOWED_CATEGORIES or not count.isdecimal():
            raise DatasetValidationError("expected composition is invalid")
        expected[category] = int(count)
    return expected


def _assert_no_sensitive_data(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if any(part in key.lower() for part in SENSITIVE_KEY_PARTS):
                raise DatasetValidationError("dataset contains a forbidden sensitive field")
            _assert_no_sensitive_data(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_sensitive_data(child)
    elif isinstance(value, str) and SENSITIVE_VALUE_PATTERN.search(value):
        raise DatasetValidationError("dataset contains a forbidden sensitive value")


def _require_keys(value: dict[str, Any], keys: set[str], *, label: str) -> None:
    if not keys <= set(value):
        raise DatasetValidationError(f"{label} is missing required fields")


def _validate_happy_case(record: dict[str, Any]) -> None:
    expected = record["expected"]
    if expected["state"] != "completed":
        raise DatasetValidationError("happy cases must terminate as completed")
    if tuple(expected["trace"]) != HAPPY_TRACE:
        raise DatasetValidationError("happy cases must use the complete deterministic tool trace")
    if tuple(expected["events"]) != HAPPY_EVENTS:
        raise DatasetValidationError("happy cases must expose the stable completed event sequence")
    if not REQUIRED_REPORT_FIELDS <= set(expected["report"]):
        raise DatasetValidationError("happy cases require the complete report contract")
    if expected["report"]["is_partial"] is not False:
        raise DatasetValidationError("happy cases cannot silently use a partial report")
    if not FORBIDDEN_HAPPY_ASSERTIONS <= set(expected["forbidden_assertions"]):
        raise DatasetValidationError("happy cases are missing forbidden behavior assertions")
    if not record["semantic_tags"]:
        raise DatasetValidationError("happy cases require at least one semantic tag")
    if set(record["semantic_tags"]).intersection(TAG_CATEGORY):
        raise DatasetValidationError("happy cases cannot hide a boundary or tool failure")


def _validate_record(record: dict[str, Any], *, sequence: int, parent_hash: str | None) -> str:
    required = {
        "schema_version",
        "case_id",
        "sequence",
        "category",
        "semantic_tags",
        "input",
        "expected",
        "parent_hash",
        "case_hash",
    }
    if set(record) != required:
        raise DatasetValidationError("case fields do not match the versioned contract")
    if record["schema_version"] != SCHEMA_VERSION or record["sequence"] != sequence:
        raise DatasetValidationError("case version or sequence is invalid")
    if not isinstance(record["case_id"], str) or not record["case_id"].startswith("phase02-"):
        raise DatasetValidationError("case id is invalid")
    if record["category"] not in ALLOWED_CATEGORIES:
        raise DatasetValidationError("case category is invalid")
    if not isinstance(record["semantic_tags"], list) or len(set(record["semantic_tags"])) != len(record["semantic_tags"]):
        raise DatasetValidationError("case semantic tags are invalid")
    if record["parent_hash"] != parent_hash:
        raise DatasetValidationError("case hash chain parent is invalid")
    if not isinstance(record["case_hash"], str) or record["case_hash"] != _canonical_hash(record):
        raise DatasetValidationError("case hash does not match canonical content")
    if not isinstance(record["input"], dict) or not isinstance(record["expected"], dict):
        raise DatasetValidationError("case input or expected result is invalid")
    _require_keys(record["input"], {"message", "history", "resume_payload"}, label="case input")
    _require_keys(
        record["expected"],
        {"state", "trace", "report", "events", "forbidden_assertions", "resolved_foods"},
        label="case expected result",
    )
    _assert_no_sensitive_data(record)
    for tag in record["semantic_tags"]:
        required_category = TAG_CATEGORY.get(tag)
        if required_category is not None and record["category"] != required_category:
            raise DatasetValidationError("semantic boundary has an invalid case category")
    if record["category"] == "happy":
        _validate_happy_case(record)
    return record["case_hash"]


def validate_dataset(
    dataset: Path, *, expected_count: int, expected_composition: dict[str, int], required_happy_tags: set[str]
) -> None:
    try:
        records = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line]
    except (OSError, json.JSONDecodeError) as error:
        raise DatasetValidationError("dataset is unreadable or contains invalid JSON") from error
    if len(records) != expected_count:
        raise DatasetValidationError("dataset case count does not match the required frozen prefix")

    parent_hash: str | None = None
    for sequence, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise DatasetValidationError("dataset records must be objects")
        parent_hash = _validate_record(record, sequence=sequence, parent_hash=parent_hash)

    composition = Counter(record["category"] for record in records)
    if dict(composition) != expected_composition:
        raise DatasetValidationError("dataset category composition does not match the required prefix")
    happy_tags = {tag for record in records if record["category"] == "happy" for tag in record["semantic_tags"]}
    if not required_happy_tags <= happy_tags:
        raise DatasetValidationError("happy prefix is missing required semantic coverage")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--expected-count", required=True, type=int)
    parser.add_argument("--expected-composition", required=True)
    parser.add_argument("--require-happy-tags", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        validate_dataset(
            arguments.dataset,
            expected_count=arguments.expected_count,
            expected_composition=_parse_composition(arguments.expected_composition),
            required_happy_tags={tag for tag in arguments.require_happy_tags.split(",") if tag},
        )
    except DatasetValidationError as error:
        print(f"dataset validation failed: {error}", file=sys.stderr)
        return 2
    print("dataset validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
