"""Fail-closed contracts for Phase 2 machine-evaluation artifacts."""

from __future__ import annotations

import json
import copy
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


def _synthetic_signoff_payload() -> dict[str, object]:
    """Exercise validator identity rules without producing a human-signoff artifact."""
    from evals.evaluate_phase2 import RUBRIC_VERSION, file_hash

    records = [json.loads(line) for line in _dataset().read_text(encoding="utf-8").splitlines()]
    dataset_hash = file_hash(_dataset())
    code_eval_hash = file_hash(Path("evals/phase2-code-eval.json"))
    reviewers = [
        {"pseudonym": "yu-nutritionist", "role": "nutritionist"},
        {"pseudonym": "chen-food-data-admin", "role": "food_composition_data_steward"},
    ]
    confirmations = {
        "food_code": True,
        "blocking_fields": True,
        "household_portion_auditability": True,
        "authoritative_values": True,
        "hard_validation": True,
    }
    reviews: list[dict[str, object]] = []
    judge_scores: list[dict[str, object]] = []
    for record in records:
        is_medium = record["category"] == "missing_ambiguity"
        for reviewer in reviewers:
            review: dict[str, object] = {
                "case_id": record["case_id"],
                "role": reviewer["role"],
                "pseudonym": reviewer["pseudonym"],
                "rubric_version": RUBRIC_VERSION,
                "dataset_hash": dataset_hash,
                "code_eval_hash": code_eval_hash,
                "confirmations": copy.deepcopy(confirmations),
            }
            if is_medium:
                review["medium_human_score"] = 4
            reviews.append(review)
        if is_medium:
            judge_scores.append(
                {
                    "case_id": record["case_id"],
                    "rubric_version": RUBRIC_VERSION,
                    "dataset_hash": dataset_hash,
                    "code_eval_hash": code_eval_hash,
                    "score": 4,
                }
            )
    return {
        "schema_version": "expert-signoff.v1",
        "rubric_version": RUBRIC_VERSION,
        "dataset_hash": dataset_hash,
        "code_eval_hash": code_eval_hash,
        "reviewers": reviewers,
        "reviews": reviews,
        "judge_scores": judge_scores,
    }


def _validate_signoff_without_machine_evidence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, payload: dict[str, object]) -> None:
    from evals import evaluate_phase2

    monkeypatch.setattr(evaluate_phase2, "verify_code_eval", lambda **_: {})
    signoff = tmp_path / "expert-signoff.json"
    signoff.write_text(json.dumps(payload), encoding="utf-8")
    evaluate_phase2.validate_signoff(
        dataset=_dataset(), code_eval=Path("evals/phase2-code-eval.json"), signoff=signoff
    )


def test_signoff_allows_a_stable_real_reviewer_to_sign_multiple_cases(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _validate_signoff_without_machine_evidence(monkeypatch, tmp_path, _synthetic_signoff_payload())


def test_signoff_rejects_duplicate_role_review_for_one_case(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from evals.evaluate_phase2 import EvaluationContractError

    payload = _synthetic_signoff_payload()
    reviews = payload["reviews"]
    assert isinstance(reviews, list)
    reviews.append(copy.deepcopy(reviews[0]))
    with pytest.raises(EvaluationContractError, match="duplicate role review"):
        _validate_signoff_without_machine_evidence(monkeypatch, tmp_path, payload)


def test_signoff_rejects_review_that_does_not_match_stable_roster_role(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from evals.evaluate_phase2 import EvaluationContractError

    payload = _synthetic_signoff_payload()
    reviews = payload["reviews"]
    assert isinstance(reviews, list) and isinstance(reviews[0], dict)
    reviews[0]["role"] = "food_composition_data_steward"
    with pytest.raises(EvaluationContractError, match="does not match reviewer roster"):
        _validate_signoff_without_machine_evidence(monkeypatch, tmp_path, payload)
