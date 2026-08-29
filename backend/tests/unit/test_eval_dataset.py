"""Unit evidence for frozen-case hash and classification guards."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.validate_dataset import DatasetValidationError, _canonical_hash, validate_dataset


REQUIRED_TAGS = {
    "direct_grams",
    "exact_household_portion",
    "unique_alias",
    "multi_item",
    "beverage_and_condiment",
}


def _dataset() -> Path:
    return Path("evals/phase02-cases.jsonl")


def _validate(path: Path) -> None:
    validate_dataset(
        path,
        expected_count=5,
        expected_composition={"happy": 5},
        required_happy_tags=REQUIRED_TAGS,
    )


def _rehash(records: list[dict[str, object]]) -> None:
    parent_hash: str | None = None
    for record in records:
        record["parent_hash"] = parent_hash
        record["case_hash"] = _canonical_hash(record)
        parent_hash = record["case_hash"]


def test_frozen_happy_prefix_has_valid_hashes_and_required_main_path_semantics() -> None:
    _validate(_dataset())


def test_happy_case_cannot_hide_out_of_catalog_or_tool_failure(tmp_path: Path) -> None:
    records = [json.loads(line) for line in _dataset().read_text(encoding="utf-8").splitlines()]
    records[0]["semantic_tags"] = ["out_of_catalog"]
    _rehash(records)
    tampered = tmp_path / "cases.jsonl"
    tampered.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")

    with pytest.raises(DatasetValidationError, match="invalid case category"):
        _validate(tampered)


def test_rewriting_an_existing_prefix_case_breaks_its_hash_chain(tmp_path: Path) -> None:
    records = [json.loads(line) for line in _dataset().read_text(encoding="utf-8").splitlines()]
    records[0]["input"]["message"] = "熟米饭 151g"
    tampered = tmp_path / "cases.jsonl"
    tampered.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")

    with pytest.raises(DatasetValidationError, match="hash"):
        _validate(tampered)
