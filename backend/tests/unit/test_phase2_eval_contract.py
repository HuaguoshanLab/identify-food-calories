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


def test_code_eval_hashes_the_real_provider_runtime_path() -> None:
    """A release cannot certify Fake-only behavior while main selects a different provider."""

    from evals.evaluate_phase2 import _implementation_hashes

    hashes = _implementation_hashes(Path(__file__).resolve().parents[2])

    assert {"provider_factory", "deepseek_adapter", "runtime"} <= set(hashes)


@pytest.fixture
def historical_implementation_baseline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test historical score aggregation without certifying today's implementation.

    Keep the evidence bytes and validator intact; only these scoring tests view
    the source baseline recorded by the historical run. Production verification
    must still reject any source drift.
    """
    from evals import evaluate_phase2

    payload = json.loads(Path("evals/phase2-code-eval.json").read_text(encoding="utf-8"))
    hashes = payload["implementation_hashes"]
    monkeypatch.setattr(evaluate_phase2, "_implementation_hashes", lambda _: dict(hashes))


def test_code_eval_rejects_source_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    from evals import evaluate_phase2

    evidence = Path("evals/phase2-code-eval.json")
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    hashes = dict(payload["implementation_hashes"])
    hashes["runtime"] = "0" * 64 if hashes["runtime"] != "0" * 64 else "1" * 64
    monkeypatch.setattr(evaluate_phase2, "_implementation_hashes", lambda _: hashes)

    with pytest.raises(evaluate_phase2.EvaluationContractError, match="implementation hash is stale"):
        evaluate_phase2.verify_code_eval(dataset=_dataset(), result=evidence)


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


def _rebind_release_inputs(signoff: dict[str, object], promptfoo: dict[str, object]) -> None:
    """Keep synthetic release assertions independent from the committed human evidence."""

    from evals.evaluate_phase2 import file_hash

    code_eval_hash = file_hash(Path("evals/phase2-code-eval.json"))
    signoff["code_eval_hash"] = code_eval_hash
    reviews = signoff.get("reviews")
    judges = signoff.get("judge_scores")
    assert isinstance(reviews, list) and isinstance(judges, list)
    for review in reviews:
        assert isinstance(review, dict)
        review["code_eval_hash"] = code_eval_hash
    for judge in judges:
        assert isinstance(judge, dict)
        judge["code_eval_hash"] = code_eval_hash
    promptfoo["code_eval_hash"] = code_eval_hash


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


def test_release_recomputes_metrics_from_hash_bound_pairs(
    tmp_path: Path, historical_implementation_baseline: None
) -> None:
    from evals.release_phase2 import build_release, verify_release

    dataset = _dataset()
    code_eval = Path("evals/phase2-code-eval.json")
    signoff = json.loads(Path("evals/expert-signoff-phase2.json").read_text(encoding="utf-8"))
    promptfoo = json.loads(Path("evals/promptfoo-release-phase2-v4.json").read_text(encoding="utf-8"))
    _rebind_release_inputs(signoff, promptfoo)
    medium_ids = [f"phase02-{number:03d}" for number in range(6, 11)]
    paired_scores = dict(zip(medium_ids, [3, 4, 4, 5, 5], strict=True))
    for review in signoff["reviews"]:
        if review["case_id"] in medium_ids:
            review["medium_human_score"] = paired_scores[review["case_id"]]
    for judge in signoff["judge_scores"]:
        judge["score"] = paired_scores[judge["case_id"]]
    promptfoo["judge_scores"] = paired_scores
    for call in promptfoo["calls"]:
        if call["case_id"] in medium_ids:
            call["judge_score"] = paired_scores[call["case_id"]]
    signoff_path = tmp_path / "signoff.json"
    promptfoo_path = tmp_path / "promptfoo.json"
    release_path = tmp_path / "release.json"
    signoff_path.write_text(json.dumps(signoff), encoding="utf-8")
    promptfoo_path.write_text(json.dumps(promptfoo), encoding="utf-8")

    release = build_release(
        dataset=dataset,
        code_eval=code_eval,
        signoff=signoff_path,
        promptfoo=promptfoo_path,
        output=release_path,
    )

    assert release["decision"] == "PASS"
    assert release["metrics"]["spearman"] == 1.0
    assert verify_release(release_path)["decision"] == "PASS"


def test_release_fails_closed_for_constant_real_medium_pairs(
    tmp_path: Path, historical_implementation_baseline: None
) -> None:
    from evals.evaluate_phase2 import EvaluationContractError
    from evals.release_phase2 import build_release, verify_release

    release_path = tmp_path / "release.json"
    signoff = json.loads(Path("evals/expert-signoff-phase2.json").read_text(encoding="utf-8"))
    promptfoo = json.loads(Path("evals/promptfoo-release-phase2-v4.json").read_text(encoding="utf-8"))
    _rebind_release_inputs(signoff, promptfoo)
    signoff_path = tmp_path / "signoff.json"
    promptfoo_path = tmp_path / "promptfoo.json"
    signoff_path.write_text(json.dumps(signoff), encoding="utf-8")
    promptfoo_path.write_text(json.dumps(promptfoo), encoding="utf-8")
    release = build_release(
        dataset=_dataset(),
        code_eval=Path("evals/phase2-code-eval.json"),
        signoff=signoff_path,
        promptfoo=promptfoo_path,
        output=release_path,
    )

    assert release["decision"] == "FAIL"
    assert release["metrics"]["spearman"] is None
    assert release["checks"]["spearman_at_least_0_70"] is False
    with pytest.raises(EvaluationContractError, match="not PASS"):
        verify_release(release_path)
