"""Strict, offline loader for the frozen weekly-review fixture catalog."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Mapping


CATALOG_FORMAT = "weekly-review-fixtures.v1"
REQUIRED_CASE_IDS = frozenset(
    f"case-{number:02d}-{slug}"
    for number, slug in (
        (1, "sufficient-variety"), (2, "sufficient-regularity"),
        (3, "sufficient-balanced"), (4, "current-week-coverage"),
        (5, "low-coverage-meals"), (6, "low-coverage-days"), (7, "backfilled-meal"),
        (8, "facts-unsupported-output"), (9, "medical-risk"),
        (10, "pregnancy-minor-risk"), (11, "eating-disorder-self-harm"),
        (12, "schema-invalid"), (13, "privacy-contamination"), (14, "timeout-unknown-disabled-budget"),
    )
)
_HEX_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_EMAIL_VALUE = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
_DENIED_FIELD_NAMES = frozenset({
    "access_token", "base64", "chain_of_thought", "email", "full_state", "image",
    "image_locator", "image_url", "original_text", "provider_body", "reasoning", "state",
    "user_original_text", "user_text",
})
_ALLOWED_PATTERNS = frozenset({"food_variety", "meal_regularity", "meal_balance", "portion_awareness"})
_ROOT_FIELDS = frozenset({"fixture_format", "catalog_version", "cases"})
_CASE_FIELDS = frozenset({"id", "title", "facts", "config", "provider_script", "expected", "ledger"})
_FACT_FIELDS = frozenset({"facts_version", "week_start", "week_end_exclusive", "week_kind", "coverage_days", "meal_count", "totals", "allowed_patterns", "coverage_sufficient", "facts_digest"})
_TOTAL_FIELDS = frozenset({"energy_kcal", "protein_g", "fat_g", "carbohydrate_g"})
_CONFIG_FIELDS = frozenset({"runtime_config_version", "provider_enabled", "call_cap", "timeout_ms", "admission"})
_SCRIPT_FIELDS = frozenset({"events", "admission_rejections"})
_EVENT_FIELDS = frozenset({"kind", "suggestions", "violation"})
_SUGGESTION_FIELDS = frozenset({"category", "text"})
_EXPECTED_FIELDS = frozenset({"stable_code", "allowed_categories", "max_model_calls", "provider_calls", "input_violation"})
_LEDGER_FIELDS = frozenset({"run_status", "failure_code", "model_calls", "invocation_count"})


class FixtureValidationError(ValueError):
    """Raised before a fixture can reach graph, provider, or ledger test code."""


@dataclass(frozen=True)
class WeeklyReviewFixture:
    """A validated catalog row with no production identity or transcript data."""

    id: str
    facts: Mapping[str, Any]
    config: Mapping[str, Any]
    provider_script: Mapping[str, Any]
    expected: Mapping[str, Any]
    ledger: Mapping[str, Any]


def load_catalog(path: str | Path) -> tuple[WeeklyReviewFixture, ...]:
    """Read a catalog only after strict shape, privacy, and invariant validation."""

    source = Path(path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise FixtureValidationError(f"unable to read fixture catalog: {error}") from error
    _validate_catalog(raw)
    return tuple(
        WeeklyReviewFixture(
            id=row["id"], facts=row["facts"], config=row["config"],
            provider_script=row["provider_script"], expected=row["expected"], ledger=row["ledger"],
        )
        for row in raw["cases"]
    )


def _validate_catalog(raw: Any) -> None:
    _mapping(raw, "catalog")
    _exact_keys(raw, _ROOT_FIELDS, "catalog")
    if raw["fixture_format"] != CATALOG_FORMAT or raw["catalog_version"] != "v1":
        raise FixtureValidationError("catalog has an unsupported fixture format or version")
    cases = raw["cases"]
    if not isinstance(cases, list) or len(cases) != len(REQUIRED_CASE_IDS):
        raise FixtureValidationError("catalog must contain exactly the frozen 14 cases")
    _reject_sensitive_content(raw)
    identifiers = [row.get("id") for row in cases if isinstance(row, dict)]
    if len(identifiers) != len(cases) or len(set(identifiers)) != len(identifiers):
        raise FixtureValidationError("catalog contains a missing or duplicate case id")
    if set(identifiers) != REQUIRED_CASE_IDS:
        missing = sorted(REQUIRED_CASE_IDS - set(identifiers))
        extra = sorted(set(identifiers) - REQUIRED_CASE_IDS)
        raise FixtureValidationError(f"catalog case ids do not match the frozen set; missing={missing}, extra={extra}")
    for row in cases:
        _validate_case(row)


def _validate_case(row: Any) -> None:
    _mapping(row, "case")
    _exact_keys(row, _CASE_FIELDS, f"case {row.get('id', '<unknown>')}")
    if not isinstance(row["id"], str) or not row["id"].startswith("case-"):
        raise FixtureValidationError("case id must be a frozen case identifier")
    if not isinstance(row["title"], str) or not row["title"].strip():
        raise FixtureValidationError(f"case {row['id']} must have a non-empty synthetic title")
    _validate_facts(row["facts"], row["id"])
    _validate_config(row["config"], row["id"])
    _validate_script(row["provider_script"], row["id"])
    _validate_expected(row["expected"], row["ledger"], row["config"], row["provider_script"], row["id"])


def _validate_facts(facts: Any, case_id: str) -> None:
    _mapping(facts, f"{case_id}.facts")
    _exact_keys(facts, _FACT_FIELDS, f"{case_id}.facts")
    if facts["facts_version"] != "weekly-facts.v1":
        raise FixtureValidationError(f"{case_id} has an unsupported facts version")
    _parse_date(facts["week_start"], f"{case_id}.facts.week_start")
    start, end = (_parse_date(facts[key], f"{case_id}.facts.{key}") for key in ("week_start", "week_end_exclusive"))
    if end <= start:
        raise FixtureValidationError(f"{case_id} has an invalid week range")
    if facts["week_kind"] not in {"completed", "current_to_date"}:
        raise FixtureValidationError(f"{case_id} has an invalid week kind")
    _bounded_int(facts["coverage_days"], 0, 7, f"{case_id}.facts.coverage_days")
    _bounded_int(facts["meal_count"], 0, 100, f"{case_id}.facts.meal_count")
    _mapping(facts["totals"], f"{case_id}.facts.totals")
    _exact_keys(facts["totals"], _TOTAL_FIELDS, f"{case_id}.facts.totals")
    for name, value in facts["totals"].items():
        _bounded_int(value, 0, 100000, f"{case_id}.facts.totals.{name}")
    patterns = facts["allowed_patterns"]
    if not isinstance(patterns, list) or len(patterns) != len(set(patterns)) or not set(patterns) <= _ALLOWED_PATTERNS:
        raise FixtureValidationError(f"{case_id} has invalid allowed patterns")
    if not isinstance(facts["coverage_sufficient"], bool) or not _HEX_DIGEST.fullmatch(facts["facts_digest"]):
        raise FixtureValidationError(f"{case_id} has invalid facts coverage or digest")


def _validate_config(config: Any, case_id: str) -> None:
    _mapping(config, f"{case_id}.config")
    _exact_keys(config, _CONFIG_FIELDS, f"{case_id}.config")
    if config["runtime_config_version"] != "weekly-review-runtime.v1":
        raise FixtureValidationError(f"{case_id} has an unsupported runtime config version")
    if not isinstance(config["provider_enabled"], bool) or config["admission"] not in {"allowed", "provider_disabled", "budget_denied"}:
        raise FixtureValidationError(f"{case_id} has invalid provider admission settings")
    _bounded_int(config["call_cap"], 0, 2, f"{case_id}.config.call_cap")
    _bounded_int(config["timeout_ms"], 1, 8000, f"{case_id}.config.timeout_ms")


def _validate_script(script: Any, case_id: str) -> None:
    _mapping(script, f"{case_id}.provider_script")
    if not set(script) <= _SCRIPT_FIELDS or "events" not in script:
        raise FixtureValidationError(f"{case_id} has unknown or missing provider script fields")
    events = script["events"]
    if not isinstance(events, list) or len(events) > 2:
        raise FixtureValidationError(f"{case_id} has too many provider script events")
    for event in events:
        _mapping(event, f"{case_id}.provider_script event")
        if not set(event) <= _EVENT_FIELDS or "kind" not in event:
            raise FixtureValidationError(f"{case_id} has invalid provider script event fields")
        kind = event["kind"]
        if kind == "result":
            if set(event) != {"kind", "suggestions"} or not isinstance(event["suggestions"], list) or not 1 <= len(event["suggestions"]) <= 3:
                raise FixtureValidationError(f"{case_id} has an invalid result script")
            for suggestion in event["suggestions"]:
                _mapping(suggestion, f"{case_id}.provider_script suggestion")
                _exact_keys(suggestion, _SUGGESTION_FIELDS, f"{case_id}.provider_script suggestion")
                if suggestion["category"] not in _ALLOWED_PATTERNS or not isinstance(suggestion["text"], str) or not suggestion["text"].strip():
                    raise FixtureValidationError(f"{case_id} has an invalid scripted suggestion")
        elif kind in {"unsafe_result", "invalid_result"}:
            if set(event) != {"kind", "violation"} or not isinstance(event["violation"], str):
                raise FixtureValidationError(f"{case_id} has an invalid rejected-result script")
        elif kind not in {"timeout", "outcome_unknown"} or set(event) != {"kind"}:
            raise FixtureValidationError(f"{case_id} has an unsupported provider script event")
    rejections = script.get("admission_rejections", [])
    if not isinstance(rejections, list) or not set(rejections) <= {"PROVIDER_DISABLED", "BUDGET_DENIED"}:
        raise FixtureValidationError(f"{case_id} has invalid admission rejection metadata")


def _validate_expected(expected: Any, ledger: Any, config: Mapping[str, Any], script: Mapping[str, Any], case_id: str) -> None:
    _mapping(expected, f"{case_id}.expected")
    if not set(expected) <= _EXPECTED_FIELDS or not {"stable_code", "allowed_categories", "max_model_calls", "provider_calls"} <= set(expected):
        raise FixtureValidationError(f"{case_id} has unknown or missing expectations")
    if not isinstance(expected["stable_code"], str) or not isinstance(expected["allowed_categories"], list) or not set(expected["allowed_categories"]) <= _ALLOWED_PATTERNS:
        raise FixtureValidationError(f"{case_id} has invalid expected code or categories")
    _bounded_int(expected["max_model_calls"], 0, 2, f"{case_id}.expected.max_model_calls")
    _bounded_int(expected["provider_calls"], 0, 2, f"{case_id}.expected.provider_calls")
    if expected["provider_calls"] > expected["max_model_calls"] or expected["max_model_calls"] > config["call_cap"]:
        raise FixtureValidationError(f"{case_id} exceeds its call cap")
    _mapping(ledger, f"{case_id}.ledger")
    _exact_keys(ledger, _LEDGER_FIELDS, f"{case_id}.ledger")
    if ledger["run_status"] not in {"completed", "abstained"} or (ledger["failure_code"] is not None and not isinstance(ledger["failure_code"], str)):
        raise FixtureValidationError(f"{case_id} has invalid minimal ledger metadata")
    _bounded_int(ledger["model_calls"], 0, 2, f"{case_id}.ledger.model_calls")
    _bounded_int(ledger["invocation_count"], 0, 2, f"{case_id}.ledger.invocation_count")
    if ledger["model_calls"] != expected["provider_calls"] or ledger["invocation_count"] != expected["provider_calls"]:
        raise FixtureValidationError(f"{case_id} ledger call counts do not match expected provider calls")
    if not config["provider_enabled"] and expected["provider_calls"] != 0:
        raise FixtureValidationError(f"{case_id} cannot call a disabled provider")
    if not config["provider_enabled"] and "PROVIDER_DISABLED" not in script.get("admission_rejections", []):
        raise FixtureValidationError(f"{case_id} must record disabled-provider admission rejection")


def _reject_sensitive_content(value: Any, path: str = "catalog") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key.casefold() in _DENIED_FIELD_NAMES:
                raise FixtureValidationError(f"{path} contains prohibited sensitive field {key!r}")
            _reject_sensitive_content(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _reject_sensitive_content(nested, f"{path}[{index}]")
    elif isinstance(value, str) and _EMAIL_VALUE.search(value):
        raise FixtureValidationError(f"{path} contains an email-like value")


def _mapping(value: Any, path: str) -> None:
    if not isinstance(value, dict):
        raise FixtureValidationError(f"{path} must be an object")


def _exact_keys(value: Mapping[str, Any], allowed: frozenset[str], path: str) -> None:
    missing, unknown = allowed - set(value), set(value) - allowed
    if missing or unknown:
        raise FixtureValidationError(f"{path} field mismatch; missing={sorted(missing)}, unknown={sorted(unknown)}")


def _parse_date(value: Any, path: str) -> date:
    if not isinstance(value, str):
        raise FixtureValidationError(f"{path} must be an ISO date")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise FixtureValidationError(f"{path} must be an ISO date") from error


def _bounded_int(value: Any, minimum: int, maximum: int, path: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise FixtureValidationError(f"{path} must be an integer between {minimum} and {maximum}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a frozen weekly-review fixture catalog.")
    parser.add_argument("--validate", metavar="CATALOG", type=Path, help="catalog JSON to validate")
    args = parser.parse_args(argv)
    if args.validate is None:
        parser.error("--validate is required")
    try:
        fixtures = load_catalog(args.validate)
    except FixtureValidationError as error:
        print(f"INVALID: {error}", file=sys.stderr)
        return 1
    print(f"VALID: {args.validate} ({len(fixtures)} frozen cases, {CATALOG_FORMAT})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
