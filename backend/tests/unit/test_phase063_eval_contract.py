"""Fail-closed contracts for the Phase 06.3 frozen retrieval evidence."""

from __future__ import annotations

import json
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

    assert evaluate.EVALUATOR_VERSION == "phase063-evaluator.v1"
    assert "SqlAlchemyHybridFoodSearchRepository" in evaluate.__doc__
    assert hasattr(evaluate, "build_release")
    assert hasattr(evaluate, "verify_release")


def test_release_verification_rejects_any_hash_or_metric_tampering(tmp_path: Path) -> None:
    from evals.phase_06_3.evaluate import EvaluationContractError, verify_release

    release = tmp_path / "release.json"
    release.write_text('{"decision":"PASS","evidence_hash":"' + "0" * 64 + '"}\n', encoding="utf-8")

    with pytest.raises(EvaluationContractError):
        verify_release(release)
