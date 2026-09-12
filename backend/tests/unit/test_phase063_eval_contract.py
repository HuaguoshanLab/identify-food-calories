"""Fail-closed contracts for the Phase 06.3 frozen retrieval evidence."""

from __future__ import annotations

import json
import hashlib
import sys
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

DATASET = BACKEND_ROOT / "evals/phase_06_3/cases.jsonl"


def _write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _rows() -> list[dict[str, object]]:
    return [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines()]


def test_dataset_covers_frozen_categories_locked_mappings_and_nonzero_denominators() -> None:
    from evals.phase_06_3.evaluate import REQUIRED_CASE_KINDS, validate_dataset

    rows = validate_dataset(DATASET)

    assert len(rows) >= 24
    assert REQUIRED_CASE_KINDS <= {row["kind"] for row in rows}
    assert any(
        row["query"] == "米饭"
        and row["expected"]["action"] == "PASS"
        and row["expected"]["target_food_ids"] == ["food:rice-v1"]
        for row in rows
    )
    locked_targets = {
        "西红柿炒鸡蛋": "food:tomato-egg-v1",
        "风干牛肉": "food:beef-jerky-v1",
        "四川烤鱼": "food:grilled-fish-v1",
        "定西土豆粉": "food:potato-noodles-v1",
        "包子": "food:pan-fried-bun-v1",
    }
    for query, target in locked_targets.items():
        record = next(row for row in rows if row["query"] == query)
        assert record["expected"]["action"] == "ASK"
        assert target in record["expected"]["target_food_ids"]
        assert record["auto_pass_allowed"] is False
    assert all(
        row["expected"]["target_food_ids"] == []
        or row["expected"]["action"] == "ASK"
        for row in rows
        if row["kind"] == "non_exact"
    )


@pytest.mark.parametrize("mutation", ["unknown_key", "order", "parent_hash", "case_hash"])
def test_dataset_rejects_schema_order_and_hash_mutations(tmp_path: Path, mutation: str) -> None:
    from evals.phase_06_3.evaluate import EvaluationContractError, validate_dataset

    rows = _rows()
    if mutation == "unknown_key":
        rows[0]["unexpected"] = True
    elif mutation == "order":
        rows[0], rows[1] = rows[1], rows[0]
    elif mutation == "parent_hash":
        rows[1]["parent_hash"] = "0" * 64
    else:
        rows[0]["case_hash"] = "0" * 64
    dataset = tmp_path / "cases.jsonl"
    _write_rows(dataset, rows)

    with pytest.raises(EvaluationContractError):
        validate_dataset(dataset)


@pytest.mark.parametrize("forbidden", ["email", "body_weight", "meal_text", "image_base64", "prompt", "provider_response", "embedding_vector"])
def test_dataset_rejects_privacy_fields_before_execution(tmp_path: Path, forbidden: str) -> None:
    from evals.phase_06_3.evaluate import EvaluationContractError, validate_dataset

    rows = _rows()
    rows[0][forbidden] = "sensitive-canary"
    dataset = tmp_path / "cases.jsonl"
    _write_rows(dataset, rows)

    with pytest.raises(EvaluationContractError, match="sensitive|privacy|forbidden"):
        validate_dataset(dataset)


def test_evaluator_exposes_hash_bound_real_postgresql_release_contract() -> None:
    """Plan 16 must not silently turn the frozen evaluation into an in-memory replay."""

    from evals.phase_06_3 import evaluate

    assert evaluate.EVALUATOR_VERSION == "phase063-evaluator.v3"
    assert "SqlAlchemyHybridFoodSearchRepository" in evaluate.__doc__
    assert hasattr(evaluate, "build_release")
    assert hasattr(evaluate, "verify_release")


def test_admin_activation_reuses_strict_evaluator_release_contract() -> None:
    """Admin activation must accept the evaluator's current hash-bound version.

    The service deliberately delegates schema, evaluator-version, and source-hash
    checks to ``verify_release`` so a future evaluator version cannot leave a
    stale, weaker copy in the activation path.
    """

    from app.admin.service import AdminService
    from evals.phase_06_3.evaluate import RELEASE_SCHEMA_VERSION

    release = AdminService._load_phase063_release(
        object(), BACKEND_ROOT / "evals/phase_06_3/release.json"
    )

    assert release["schema_version"] == RELEASE_SCHEMA_VERSION
    assert release["decision"] == "PASS"


def test_release_verification_rejects_any_hash_or_metric_tampering(tmp_path: Path) -> None:
    from evals.phase_06_3.evaluate import EvaluationContractError, verify_release

    release = tmp_path / "release.json"
    release.write_text('{"decision":"PASS","evidence_hash":"' + "0" * 64 + '"}\n', encoding="utf-8")

    with pytest.raises(EvaluationContractError):
        verify_release(release)


def test_release_verification_rejects_graph_output_drift_even_when_call_counts_match(tmp_path: Path) -> None:
    """A graph invocation count is not evidence that its retrieval semantics agree."""

    from evals.phase_06_3.evaluate import EvaluationContractError, verify_release

    release = tmp_path / "release.json"
    payload = json.loads((BACKEND_ROOT / "evals/phase_06_3/release.json").read_text(encoding="utf-8"))
    # Preserve the counter shape and valid per-projection DTO shape, but make the
    # meal graph return a distinct safe ASK result.  A rehashed report must still
    # fail because the recorded parity assertion no longer matches its evidence.
    payload["cases"][0]["graph_semantics"]["meal"] = {
        "action": "ASK",
        "selected_id": None,
        "candidate_ids": ["food:apple-v1"],
            "relation_labels": ["同类食物"],
    }
    _write_rehashed_release(release, payload)

    with pytest.raises(EvaluationContractError, match="flow semantics"):
        verify_release(release)


def _write_rehashed_release(path: Path, payload: dict[str, object]) -> None:
    evidence = {key: value for key, value in payload.items() if key != "evidence_hash"}
    payload["evidence_hash"] = hashlib.sha256(
        json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


@pytest.mark.parametrize("mutation", ["top_level", "case_field", "non_hex", "current_source_hash"])
def test_release_verification_rejects_schema_and_current_source_binding_drift(tmp_path: Path, mutation: str) -> None:
    from evals.phase_06_3.evaluate import EvaluationContractError, verify_release

    release = tmp_path / "release.json"
    payload = json.loads((BACKEND_ROOT / "evals/phase_06_3/release.json").read_text(encoding="utf-8"))
    if mutation == "top_level":
        payload["unexpected"] = "forbidden"
    elif mutation == "case_field":
        payload["cases"][0]["unexpected"] = "forbidden"
    elif mutation == "non_hex":
        payload["input_hashes"]["dataset_sha256"] = "g" * 64
    else:
        payload["input_hashes"]["search_policy_sha256"] = "0" * 64
    _write_rehashed_release(release, payload)

    with pytest.raises(EvaluationContractError):
        verify_release(release)
