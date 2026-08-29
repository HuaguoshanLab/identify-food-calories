"""Fail-closed contracts for Phase 2 machine-evaluation artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _dataset() -> Path:
    return Path("evals/phase02-cases.jsonl")


def test_code_eval_rejects_expected_only_static_results(tmp_path: Path) -> None:
    from evals.evaluate_phase2 import EvaluationContractError, verify_code_eval

    records = [json.loads(line) for line in _dataset().read_text(encoding="utf-8").splitlines()]
    static_result = {
        "schema_version": "phase2-code-eval.v1",
        "dataset_hash": "not-a-real-dataset-hash",
        "cases": [
            {"case_id": record["case_id"], "observed": record["expected"]}
            for record in records
        ],
    }
    result_path = tmp_path / "static.json"
    result_path.write_text(json.dumps(static_result), encoding="utf-8")

    with pytest.raises(EvaluationContractError, match="execution evidence"):
        verify_code_eval(dataset=_dataset(), result=result_path)


def test_release_failure_fixtures_cover_each_required_gate() -> None:
    from evals.evaluate_phase2 import REQUIRED_FAILURE_FIXTURES, load_failure_fixtures

    fixtures = load_failure_fixtures(Path("evals/release-failures.json"))
    assert REQUIRED_FAILURE_FIXTURES <= {fixture["id"] for fixture in fixtures}
