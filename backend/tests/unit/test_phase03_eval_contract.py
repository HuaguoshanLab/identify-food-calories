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


def test_replay_pass_explicitly_excludes_real_model_and_image_lifecycle(tmp_path: Path) -> None:
    from evals.evaluate_phase3 import build_release

    release = build_release(dataset=DATASET, output=tmp_path / "release.json")
    assert release["decision"] == "PASS"
    assert release["evidence_scope"] == "synthetic_provider_replay"
    assert release["real_model_evaluated"] is False
    assert release["real_image_lifecycle_evaluated"] is False


def test_cli_returns_failure_when_valid_replay_observations_fail_the_gate(tmp_path: Path) -> None:
    from evals.evaluate_phase3 import _hash, main

    rows = [json.loads(line) for line in DATASET.read_text().splitlines()]
    rows[0]["replay"]["items"][0]["grams"] = "999"
    parent = None
    for row in rows:
        row["parent_hash"] = parent
        row["case_hash"] = _hash({key: value for key, value in row.items() if key != "case_hash"})
        parent = row["case_hash"]
    dataset = tmp_path / "cases.jsonl"
    dataset.write_text("\n".join(json.dumps(row) for row in rows))
    assert main(["--dataset", str(dataset), "--output", str(tmp_path / "report.json")]) == 1
