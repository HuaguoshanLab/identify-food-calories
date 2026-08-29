"""Build a fail-closed Phase 2 release report from immutable evaluation evidence.

This module is deliberately separate from ``evaluate_phase2.py``.  The latter's digest is
part of the already-reviewed code-evaluation artifact, so adding release-reporting code to it
would invalidate a genuine expert sign-off without changing the evaluated product behavior.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:  # Support the documented direct CLI form.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals.evaluate_phase2 import (
    EvaluationContractError,
    _canonical_json,
    _dataset_contract,
    _percent,
    _read_json,
    _sha256_bytes,
    file_hash,
    spearman,
    validate_signoff,
    verify_code_eval,
)


RELEASE_SCHEMA_VERSION = "phase2-release.v1"
RELEASE_THRESHOLDS = {
    "critical_pass_percent": 100.0,
    "high_pass_percent": 95.0,
    "medium_average": 4.0,
    "spearman": 0.70,
}
FORBIDDEN_MACHINE_FIELDS = frozenset(
    {"api_key", "prompt", "output", "response", "reasoning", "stderr", "vars"}
)


def _assertion_percent(code_eval: dict[str, Any], severity: str) -> float:
    cases = code_eval.get("cases")
    if not isinstance(cases, list):
        raise EvaluationContractError("code eval cases are missing for release")
    values: list[bool] = []
    for case in cases:
        assertions = case.get("assertions") if isinstance(case, dict) else None
        group = assertions.get(severity) if isinstance(assertions, dict) else None
        if not isinstance(group, dict) or not group or not all(
            isinstance(value, bool) for value in group.values()
        ):
            raise EvaluationContractError("code eval assertions are incomplete for release")
        values.extend(group.values())
    return _percent(values)


def _release_promptfoo(
    *, promptfoo: Path, dataset_hash: str, code_eval_hash: str, medium_case_ids: set[str]
) -> tuple[dict[str, Any], dict[str, int], dict[str, int]]:
    payload = _read_json(promptfoo, label="Promptfoo machine evidence")
    if FORBIDDEN_MACHINE_FIELDS & set(payload):
        raise EvaluationContractError("Promptfoo machine evidence contains forbidden raw fields")
    fixed_contract = {
        "schema_version": "phase2-promptfoo-release.v1",
        "status": "completed",
        "dataset_hash": dataset_hash,
        "code_eval_hash": code_eval_hash,
        "calls_authorized": 36,
        "calls_attempted": 36,
        "calls_completed": 36,
        "max_concurrency": 1,
        "cache": "disabled",
        "max_retries": 0,
    }
    if any(payload.get(key) != value for key, value in fixed_contract.items()):
        raise EvaluationContractError("Promptfoo machine evidence does not satisfy the fixed release contract")
    calls = payload.get("calls")
    if not isinstance(calls, list) or len(calls) != 36:
        raise EvaluationContractError("Promptfoo machine evidence call set is incomplete")
    failures = {"network_failure": 0, "product_failure": 0, "other_failure": 0}
    repeated_scores: dict[str, list[int]] = {case_id: [] for case_id in medium_case_ids}
    for call in calls:
        if not isinstance(call, dict) or FORBIDDEN_MACHINE_FIELDS & set(call):
            raise EvaluationContractError("Promptfoo call evidence is invalid or unsafe")
        if call.get("status") != "completed":
            category = call.get("failure_category")
            failures[
                "network_failure"
                if category == "network_failure"
                else "product_failure"
                if category == "product_failure"
                else "other_failure"
            ] += 1
            continue
        case_id, score = call.get("case_id"), call.get("judge_score")
        if case_id in repeated_scores:
            if type(score) is not int or not 1 <= score <= 5:
                raise EvaluationContractError("Promptfoo Medium score is missing or invalid")
            repeated_scores[str(case_id)].append(score)
    if any(failures.values()):
        raise EvaluationContractError("Promptfoo network and product failures cannot produce a release PASS")
    scores: dict[str, int] = {}
    for case_id, values in repeated_scores.items():
        if len(values) != 3 or len(set(values)) != 1:
            raise EvaluationContractError("Promptfoo Medium scores are incomplete or unstable")
        scores[case_id] = values[0]
    if payload.get("judge_scores") != scores:
        raise EvaluationContractError("Promptfoo declared Judge scores do not match repeated call evidence")
    return payload, scores, failures


def build_release(
    *, dataset: Path, code_eval: Path, signoff: Path, promptfoo: Path, output: Path
) -> dict[str, Any]:
    records = _dataset_contract(dataset)
    code_payload = verify_code_eval(dataset=dataset, result=code_eval)
    signoff_payload = validate_signoff(dataset=dataset, code_eval=code_eval, signoff=signoff)
    dataset_hash, code_eval_hash = file_hash(dataset), file_hash(code_eval)
    medium_case_ids = {
        str(record["case_id"])
        for record in records
        if record["category"] == "missing_ambiguity"
    }
    promptfoo_payload, machine_scores, failure_counts = _release_promptfoo(
        promptfoo=promptfoo,
        dataset_hash=dataset_hash,
        code_eval_hash=code_eval_hash,
        medium_case_ids=medium_case_ids,
    )
    human_by_case: dict[str, list[int]] = {case_id: [] for case_id in medium_case_ids}
    for review in signoff_payload["reviews"]:
        if isinstance(review, dict) and review.get("case_id") in human_by_case:
            score = review.get("medium_human_score")
            if type(score) is not int or not 1 <= score <= 5:
                raise EvaluationContractError("expert Medium score is missing or invalid for release")
            human_by_case[str(review["case_id"])].append(score)
    signoff_judges = {
        str(item.get("case_id")): item.get("score")
        for item in signoff_payload["judge_scores"]
        if isinstance(item, dict)
    }
    if signoff_judges != machine_scores:
        raise EvaluationContractError("expert signoff Judge scores do not match Promptfoo machine evidence")
    paired_human: list[int] = []
    paired_judge: list[int] = []
    for case_id in sorted(medium_case_ids):
        scores = human_by_case[case_id]
        if len(scores) != 2:
            raise EvaluationContractError("each Medium case requires two paired expert scores")
        paired_human.extend(scores)
        paired_judge.extend([machine_scores[case_id]] * len(scores))
    critical_percent = _assertion_percent(code_payload, "critical")
    high_percent = _assertion_percent(code_payload, "high")
    human_average = round(sum(paired_human) / len(paired_human), 4)
    judge_average = round(sum(paired_judge) / len(paired_judge), 4)
    checks: dict[str, bool] = {
        "critical_100_percent": critical_percent >= RELEASE_THRESHOLDS["critical_pass_percent"],
        "high_at_least_95_percent": high_percent >= RELEASE_THRESHOLDS["high_pass_percent"],
        "medium_human_average_at_least_4": human_average >= RELEASE_THRESHOLDS["medium_average"],
        "medium_judge_average_at_least_4": judge_average >= RELEASE_THRESHOLDS["medium_average"],
        "no_score_one": 1 not in paired_human and 1 not in paired_judge,
    }
    try:
        correlation = spearman(paired_human, paired_judge)
    except EvaluationContractError:
        correlation = None
        checks["spearman_at_least_0_70"] = False
    else:
        checks["spearman_at_least_0_70"] = correlation >= RELEASE_THRESHOLDS["spearman"]
    report: dict[str, Any] = {
        "schema_version": RELEASE_SCHEMA_VERSION,
        "decision": "PASS" if all(checks.values()) else "FAIL",
        "input_hashes": {
            "dataset_hash": dataset_hash,
            "code_eval_hash": code_eval_hash,
            "signoff_hash": file_hash(signoff),
            "promptfoo_hash": file_hash(promptfoo),
        },
        "promptfoo_contract": {
            "config_hash": promptfoo_payload.get("config_hash"),
            "judge_prompt_contract_version": promptfoo_payload.get("judge_prompt_contract_version"),
            "judge_prompt_hash": promptfoo_payload.get("judge_prompt_hash"),
            "judge_response_format": promptfoo_payload.get("judge_response_format"),
            "judge_thinking": promptfoo_payload.get("judge_thinking"),
            "failure_counts": failure_counts,
        },
        "thresholds": RELEASE_THRESHOLDS,
        "metrics": {
            "critical_pass_percent": critical_percent,
            "high_pass_percent": high_percent,
            "medium_human_average": human_average,
            "medium_judge_average": judge_average,
            "paired_score_count": len(paired_human),
            "spearman": correlation,
        },
        "checks": checks,
    }
    report["evidence_hash"] = _sha256_bytes(_canonical_json(report))
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def verify_release(release: Path) -> dict[str, Any]:
    payload = _read_json(release, label="release report")
    evidence_hash = payload.pop("evidence_hash", None)
    if (
        payload.get("schema_version") != RELEASE_SCHEMA_VERSION
        or not isinstance(evidence_hash, str)
        or evidence_hash != _sha256_bytes(_canonical_json(payload))
    ):
        raise EvaluationContractError("release report hash or schema is invalid")
    payload["evidence_hash"] = evidence_hash
    if payload.get("decision") != "PASS":
        raise EvaluationContractError("release decision is not PASS")
    checks = payload.get("checks")
    if not isinstance(checks, dict) or not checks or not all(value is True for value in checks.values()):
        raise EvaluationContractError("release report contains an unmet gate")
    return payload


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    release = commands.add_parser("release")
    release.add_argument("--dataset", type=Path, required=True)
    release.add_argument("--code-eval", type=Path, required=True)
    release.add_argument("--signoff", type=Path, required=True)
    release.add_argument("--promptfoo", type=Path, required=True)
    release.add_argument("--output", type=Path, required=True)
    verify = commands.add_parser("verify-release")
    verify.add_argument("release", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if arguments.command == "release":
            report = build_release(
                dataset=arguments.dataset,
                code_eval=arguments.code_eval,
                signoff=arguments.signoff,
                promptfoo=arguments.promptfoo,
                output=arguments.output,
            )
            print(f"release decision: {report['decision']}")
            return 0
        verify_release(arguments.release)
    except EvaluationContractError as error:
        print(f"release contract rejected: {error}", file=sys.stderr)
        return 2
    print("release contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
