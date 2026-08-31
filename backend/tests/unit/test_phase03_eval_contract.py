"""Fail-closed contracts for Phase 3 frozen multimodal evaluation evidence."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


DATASET = Path("evals/phase03-cases.jsonl")


def test_frozen_phase3_dataset_covers_success_and_required_failure_paths() -> None:
    from evals.evaluate_phase3 import REQUIRED_CASE_KINDS, validate_phase3_dataset

    records = validate_phase3_dataset(DATASET)

    assert REQUIRED_CASE_KINDS <= {record["kind"] for record in records}
    assert all("expected" in record for record in records)


def test_release_fails_closed_for_dataset_hash_drift(tmp_path: Path) -> None:
    from evals.evaluate_phase3 import EvaluationContractError, build_release

    dataset = tmp_path / "cases.jsonl"
    dataset.write_text(DATASET.read_text(encoding="utf-8"), encoding="utf-8")
    records = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines()]
    records[0]["expected"]["catalog_food_ids"] = []
    dataset.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")

    with pytest.raises(EvaluationContractError, match="case hash"):
        build_release(dataset=dataset, output=tmp_path / "release.json")


def test_release_fails_when_any_critical_safety_assertion_fails(tmp_path: Path) -> None:
    from evals.evaluate_phase3 import build_release

    release = build_release(
        dataset=DATASET,
        output=tmp_path / "release.json",
        forced_assertion_failure="dangerous_image_rejected",
    )

    assert release["decision"] == "FAIL"
    assert release["checks"]["critical_safety_assertions"] is False
