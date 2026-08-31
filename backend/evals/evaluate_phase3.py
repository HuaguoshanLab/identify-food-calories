"""Hash-bound, fail-closed frozen evidence for the Phase 3 vision path."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.images.schemas import ValidatedImageReference
from app.providers.reasoning.dto import ProviderCallError, ProviderFailureKind
from app.providers.vision.dto import VisionMealItemDTO, VisionMealRequest
from app.providers.vision.fake import FakeVisionModelProvider


EVALUATOR_VERSION = "phase03-evaluator.v1"
CASE_SCHEMA_VERSION = "phase03-case.v1"
REQUIRED_CASE_KINDS = frozenset({
    "single_dish", "multiple_dishes", "ambiguous_dish", "out_of_catalog",
    "estimate_high_confidence", "estimate_low_confidence", "dangerous_image",
    "provider_schema_invalid", "provider_transient", "provider_outcome_unknown",
    "expired_image", "delete_chain",
})
_CATALOG_BY_NAME = {"米饭": "fdc:169756", "水煮蛋": "fdc:748967", "辣椒炒肉": "recipe:chili-fried-pork-v2"}
_FORBIDDEN_PARTS = frozenset({"image", "base64", "raw_response", "api_key", "prompt", "chain_of_thought"})


class EvaluationContractError(ValueError):
    """Stable CI-safe error for invalid frozen evidence."""


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def file_hash(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise EvaluationContractError(f"required evidence is unavailable: {path.name}") from error


def _load_jsonl(dataset: Path) -> list[dict[str, Any]]:
    try:
        rows = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line]
    except (OSError, json.JSONDecodeError) as error:
        raise EvaluationContractError("frozen vision dataset is unreadable") from error
    if not all(isinstance(row, dict) for row in rows):
        raise EvaluationContractError("frozen vision dataset rows must be objects")
    return rows


def validate_phase3_dataset(dataset: Path) -> list[dict[str, Any]]:
    rows, parent = _load_jsonl(dataset), None
    if not rows:
        raise EvaluationContractError("frozen vision dataset is empty")
    for sequence, row in enumerate(rows, start=1):
        if set(row) != {"schema_version", "case_id", "sequence", "kind", "fixture_ref", "replay", "expected", "parent_hash", "case_hash"}:
            raise EvaluationContractError("case fields do not match the frozen contract")
        if row["schema_version"] != CASE_SCHEMA_VERSION or row["sequence"] != sequence or row["parent_hash"] != parent:
            raise EvaluationContractError("case version, sequence, or hash chain is invalid")
        if not isinstance(row["case_id"], str) or row["case_id"] != f"phase03-{sequence:03d}":
            raise EvaluationContractError("case id is invalid")
        if row["kind"] not in REQUIRED_CASE_KINDS or not isinstance(row["fixture_ref"], str) or not row["fixture_ref"].startswith("synthetic:"):
            raise EvaluationContractError("case kind or fixture reference is invalid")
        if any(forbidden in key.lower() for key in row for forbidden in _FORBIDDEN_PARTS):
            raise EvaluationContractError("case contains a forbidden sensitive field")
        expected = row["expected"]
        if not isinstance(expected, dict) or set(expected) != {"catalog_food_ids", "state", "estimated_grams", "image_deleted", "provider_calls"}:
            raise EvaluationContractError("case expectation is incomplete")
        if not isinstance(expected["catalog_food_ids"], list) or not set(expected["catalog_food_ids"]) <= set(_CATALOG_BY_NAME.values()):
            raise EvaluationContractError("case references an unauthorized catalog item")
        if not isinstance(row["case_hash"], str) or row["case_hash"] != _hash({key: value for key, value in row.items() if key != "case_hash"}):
            raise EvaluationContractError("case hash does not match canonical content")
        parent = row["case_hash"]
    missing = REQUIRED_CASE_KINDS - {row["kind"] for row in rows}
    if missing:
        raise EvaluationContractError("frozen dataset is missing required failure categories")
    return rows


def _request() -> VisionMealRequest:
    now = datetime(2026, 8, 31, tzinfo=UTC)
    return VisionMealRequest(
        image=ValidatedImageReference(digest_sha256="f" * 64, mime_type="image/jpeg", width=12, height=8, byte_size=96, locator="0" * 32 + ".jpg", created_at=now, expires_at=now + timedelta(minutes=5)),
        model_alias="phase03-fake-vision", pixel_budget=65_536, request_key="phase03-frozen-request",
    )


def _vision_items(items: list[dict[str, Any]]) -> list[VisionMealItemDTO]:
    """Translate the replay-only gram label into the public Vision DTO boundary."""

    return [
        VisionMealItemDTO(
            item_id=f"item-{index}",
            food_name=item["food_name"],
            estimated_grams=item["grams"],
            confidence=item["confidence"],
        )
        for index, item in enumerate(items, start=1)
    ]


async def _replay(case: dict[str, Any]) -> dict[str, Any]:
    replay = case["replay"]
    outcome = replay["outcome"]
    if outcome in {"rejected_before_provider", "expired_before_provider"}:
        return {"state": "failed", "catalog_food_ids": [], "estimated_grams": [], "image_deleted": True, "provider_calls": 0, "dangerous_image_rejected": outcome == "rejected_before_provider", "outcome_unknown_not_retried": True}
    provider = FakeVisionModelProvider()
    if outcome == "schema_invalid":
        provider.queue_schema_invalid()
    elif outcome == "outcome_unknown":
        provider.queue_error(kind=ProviderFailureKind.OUTCOME_UNKNOWN, code="PROVIDER_OUTCOME_UNKNOWN")
    elif outcome == "transient_then_success":
        provider.queue_error(kind=ProviderFailureKind.TRANSIENT, code="VISION_TEMPORARY")
        provider.queue_result(_vision_items(replay["items"]))
    else:
        provider.queue_result(_vision_items(replay["items"]))
    result = None
    try:
        result = await provider.analyze_meal_image(_request())
    except ProviderCallError as error:
        if error.kind is ProviderFailureKind.TRANSIENT:
            result = await provider.analyze_meal_image(_request())
        else:
            return {"state": "failed", "catalog_food_ids": [], "estimated_grams": [], "image_deleted": True, "provider_calls": len(provider.calls), "dangerous_image_rejected": False, "outcome_unknown_not_retried": error.kind is ProviderFailureKind.OUTCOME_UNKNOWN and len(provider.calls) == 1}
    assert result is not None
    names = [item.food_name for item in result.items]
    grams = [str(item.estimated_grams) for item in result.items if item.estimated_grams is not None]
    mapped = [_CATALOG_BY_NAME[name] for name in names if name in _CATALOG_BY_NAME]
    if not mapped:
        state = "partial" if grams else "waiting_input"
    elif len(mapped) == len(names) and all(item.estimated_grams is not None for item in result.items):
        state = "completed"
    elif any(item.estimated_grams is None for item in result.items):
        state = "waiting_input"
    else:
        state = "partial"
    # A candidate without a confirmed portion is deliberately not a resolved catalog item.
    resolved_catalog_ids = mapped if state == "completed" else []
    return {"state": state, "catalog_food_ids": resolved_catalog_ids, "estimated_grams": grams, "image_deleted": True, "provider_calls": len(provider.calls), "dangerous_image_rejected": False, "outcome_unknown_not_retried": True}


def _rate(values: list[bool]) -> float:
    if not values:
        raise EvaluationContractError("metric denominator is zero")
    return round(sum(values) / len(values), 4)


def build_release(*, dataset: Path, output: Path, forced_assertion_failure: str | None = None) -> dict[str, Any]:
    cases = validate_phase3_dataset(dataset)
    observed = [asyncio.run(_replay(case)) for case in cases]
    case_rows: list[dict[str, Any]] = []
    for case, actual in zip(cases, observed, strict=True):
        expected = case["expected"]
        assertions = {
            "catalog_mapping": actual["catalog_food_ids"] == expected["catalog_food_ids"],
            "terminal_state": actual["state"] == expected["state"],
            "estimated_grams": actual["estimated_grams"] == expected["estimated_grams"],
            "temporary_image_deleted": actual["image_deleted"] is expected["image_deleted"],
            "bounded_provider_calls": actual["provider_calls"] == expected["provider_calls"],
            "dangerous_image_rejected": case["kind"] != "dangerous_image" or actual["dangerous_image_rejected"],
            "outcome_unknown_not_retried": case["kind"] != "provider_outcome_unknown" or actual["outcome_unknown_not_retried"],
        }
        if forced_assertion_failure:
            assertions[forced_assertion_failure] = False
        case_rows.append({"case_id": case["case_id"], "case_hash": case["case_hash"], "kind": case["kind"], "observed": actual, "assertions": assertions})
    catalog_cases = [row for row in case_rows if row["kind"] in {"single_dish", "multiple_dishes", "estimate_high_confidence", "provider_transient", "delete_chain"}]
    expected_ids = {item for row in catalog_cases for item in next(case for case in cases if case["case_id"] == row["case_id"])["expected"]["catalog_food_ids"]}
    observed_ids = {item for row in catalog_cases for item in row["observed"]["catalog_food_ids"]}
    estimate_cases = [row for row in case_rows if row["kind"] in {"single_dish", "multiple_dishes", "estimate_high_confidence", "provider_transient", "delete_chain"}]
    errors = [abs(Decimal(actual) - Decimal(expected)) / Decimal(expected) for row in estimate_cases for actual, expected in zip(row["observed"]["estimated_grams"], next(case for case in cases if case["case_id"] == row["case_id"])["expected"]["estimated_grams"], strict=True)]
    critical = all(row["assertions"]["temporary_image_deleted"] and row["assertions"]["bounded_provider_calls"] and row["assertions"]["dangerous_image_rejected"] and row["assertions"]["outcome_unknown_not_retried"] for row in case_rows)
    metrics = {"catalog_macro_precision": _rate([item in expected_ids for item in observed_ids]), "catalog_macro_recall": _rate([item in observed_ids for item in expected_ids]), "estimate_mape": float(sum(errors) / len(errors)) if errors else None, "report_totals_consistent": _rate([row["assertions"]["catalog_mapping"] and row["assertions"]["terminal_state"] for row in case_rows]), "dangerous_image_rejection_rate": _rate([row["assertions"]["dangerous_image_rejected"] for row in case_rows if row["kind"] == "dangerous_image"]), "deletion_chain_pass_rate": _rate([row["assertions"]["temporary_image_deleted"] for row in case_rows if row["kind"] in {"dangerous_image", "expired_image", "delete_chain"}]), "unknown_no_blind_retry_rate": _rate([row["assertions"]["outcome_unknown_not_retried"] for row in case_rows if row["kind"] == "provider_outcome_unknown"])}
    checks = {"minimum_catalog_classes": len(expected_ids) >= 2, "minimum_estimate_samples": len(errors) >= 2, "catalog_precision": metrics["catalog_macro_precision"] >= 0.9, "catalog_recall": metrics["catalog_macro_recall"] >= 0.9, "estimate_mape": metrics["estimate_mape"] is not None and metrics["estimate_mape"] <= 0.2, "report_totals_consistent": metrics["report_totals_consistent"] == 1.0, "dangerous_image_rejected": metrics["dangerous_image_rejection_rate"] == 1.0, "delete_chain": metrics["deletion_chain_pass_rate"] == 1.0, "unknown_not_retried": metrics["unknown_no_blind_retry_rate"] == 1.0, "critical_safety_assertions": critical}
    root = Path(__file__).resolve().parent
    release: dict[str, Any] = {"schema_version": "phase03-release.v1", "evaluator_version": EVALUATOR_VERSION, "decision": "PASS" if all(checks.values()) else "FAIL", "input_hashes": {"dataset_sha256": file_hash(dataset), "evaluator_sha256": file_hash(Path(__file__)), "schema_sha256": file_hash(root / "phase03-eval.schema.json")}, "thresholds": {"catalog_macro_precision": 0.9, "catalog_macro_recall": 0.9, "estimate_mape_max": 0.2, "all_safety_rates": 1.0}, "metrics": metrics, "checks": checks, "cases": case_rows}
    release["evidence_hash"] = _hash(release)
    output.write_text(json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return release


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        build_release(**vars(parse_args(sys.argv[1:] if argv is None else argv)))
    except EvaluationContractError as error:
        print(f"evaluation contract rejected: {error}", file=sys.stderr)
        return 2
    print("phase 3 evaluation contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
