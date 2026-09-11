"""Explicit, payload-free mirror for an already-complete Phase 06.3 release.

This module is deliberately outside the application runtime.  Phoenix remains the
only online tracing path; importing this file does not import the Langfuse SDK or
read its credentials.  The optional CLI validates a synthetic, hash-bound report
before it creates a Langfuse client and exports a deliberately smaller projection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


_TOP_LEVEL_FIELDS = frozenset({"cases", "decision", "evaluator_version", "evidence_hash", "input_hashes", "metrics", "schema_version", "snapshot"})
_CASE_FIELDS = frozenset({"action", "assertions", "candidate_ids", "case_hash", "case_id", "exact_sql", "graph_calls", "text_sql", "vector_sql"})
_ASSERTION_FIELDS = frozenset({"action", "candidate_bound", "meal_graph", "planning_graph", "targets"})
_HASH_FIELDS = frozenset({"dataset_sha256", "evaluator_sha256", "search_policy_sha256"})
_METRIC_FIELDS = frozenset({"action_pass_rate", "case_count", "exact_sql_cases", "meal_graph_entries", "meal_tool_search_calls", "planning_graph_entries", "planning_tool_compose_calls", "planning_tool_target_calls", "target_recall", "text_sql_cases", "vector_sql_cases"})
_SNAPSHOT_FIELDS = frozenset({"fixture", "food_labels"})
_ID = re.compile(r"^phase063-[0-9]{3}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_FOOD_ID = re.compile(r"^food:[a-z0-9-]+-v[0-9]+$")


class LangfusePublishError(ValueError):
    """The experiment mirror rejects any report that is not exact safe evidence."""


class LangfuseClient(Protocol):
    def start_as_current_observation(self, **payload: object) -> Any: ...

    def create_score(self, **payload: object) -> None: ...

    def flush(self) -> None: ...


@dataclass(frozen=True)
class PublishResult:
    evidence_hash: str
    published_cases: int


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _reject_unknown_fields(value: Mapping[str, object], allowed: frozenset[str], *, location: str) -> None:
    fields = set(value)
    # The validated report has a small number of safe, historical keys such as
    # ``vector_sql_cases``.  Reject by exact schema, not substring, so that safe
    # aggregate counter is not mistaken for a query vector payload.
    if fields != allowed:
        raise LangfusePublishError(f"{location} violates the exact safe allowlist")


def _load_safe_release(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError) as error:
        raise LangfusePublishError("release evidence is unreadable") from error
    if not isinstance(payload, dict):
        raise LangfusePublishError("release evidence must be an object")
    _reject_unknown_fields(payload, _TOP_LEVEL_FIELDS, location="release")
    if not isinstance(payload["schema_version"], str) or not isinstance(payload["evaluator_version"], str):
        raise LangfusePublishError("release versions are invalid")
    _validate_hashes(payload["input_hashes"])
    _validate_metrics(payload["metrics"])
    _validate_snapshot(payload["snapshot"])
    cases = payload["cases"]
    if not isinstance(cases, list) or not cases:
        raise LangfusePublishError("release has no cases")
    for case in cases:
        _validate_case(case)
    evidence_hash = payload["evidence_hash"]
    evidence = {key: value for key, value in payload.items() if key != "evidence_hash"}
    if payload["decision"] != "PASS" or not isinstance(evidence_hash, str) or not _HASH.fullmatch(evidence_hash) or hashlib.sha256(_canonical(evidence)).hexdigest() != evidence_hash:
        raise LangfusePublishError("release must be a completed PASS with a valid evidence hash")
    return payload


def _validate_hashes(value: object) -> None:
    if not isinstance(value, dict):
        raise LangfusePublishError("input hashes violate the exact safe allowlist")
    _reject_unknown_fields(value, _HASH_FIELDS, location="input hashes")
    if not all(isinstance(item, str) and _HASH.fullmatch(item) for item in value.values()):
        raise LangfusePublishError("input hashes are invalid")


def _validate_metrics(value: object) -> None:
    if not isinstance(value, dict):
        raise LangfusePublishError("metrics violate the exact safe allowlist")
    _reject_unknown_fields(value, _METRIC_FIELDS, location="metrics")
    if not all(isinstance(item, int | float) and not isinstance(item, bool) for item in value.values()):
        raise LangfusePublishError("locked scores are invalid")


def _validate_snapshot(value: object) -> None:
    if not isinstance(value, dict):
        raise LangfusePublishError("snapshot violates the exact safe allowlist")
    _reject_unknown_fields(value, _SNAPSHOT_FIELDS, location="snapshot")
    if not isinstance(value["fixture"], str) or not value["fixture"].startswith("synthetic:") or not isinstance(value["food_labels"], list) or not all(isinstance(item, str) and _FOOD_ID.fullmatch(item) for item in value["food_labels"]):
        raise LangfusePublishError("snapshot contains unsafe content")


def _validate_case(value: object) -> None:
    if not isinstance(value, dict):
        raise LangfusePublishError("case is invalid")
    _reject_unknown_fields(value, _CASE_FIELDS, location="case")
    if value["action"] not in {"PASS", "ASK", "FAIL"} or not isinstance(value["case_id"], str) or not _ID.fullmatch(value["case_id"]) or not isinstance(value["case_hash"], str) or not _HASH.fullmatch(value["case_hash"]):
        raise LangfusePublishError("case identity is invalid")
    if not isinstance(value["candidate_ids"], list) or not all(isinstance(item, str) and _FOOD_ID.fullmatch(item) for item in value["candidate_ids"]):
        raise LangfusePublishError("case candidate identifiers are invalid")
    assertions = value["assertions"]
    if not isinstance(assertions, dict):
        raise LangfusePublishError("case assertions are invalid")
    _reject_unknown_fields(assertions, _ASSERTION_FIELDS, location="case assertions")
    if not all(isinstance(item, bool) for item in assertions.values()):
        raise LangfusePublishError("case assertions are invalid")
    if not all(isinstance(value[key], int) and value[key] >= 0 for key in ("exact_sql", "text_sql", "vector_sql")) or not isinstance(value["graph_calls"], dict):
        raise LangfusePublishError("case counters are invalid")


def _default_client_factory() -> LangfuseClient:
    # Local import makes normal app, evaluator and CI paths incapable of importing Langfuse.
    from langfuse import Langfuse

    return Langfuse()


def publish_release(path: Path, *, client_factory: Callable[[], LangfuseClient] | None = None) -> PublishResult:
    """Mirror only validated synthetic evidence, without changing report bytes or decision."""

    before = path.read_bytes()
    release = _load_safe_release(path)
    client = (client_factory or _default_client_factory)()
    for case in release["cases"]:
        assert isinstance(case, dict)
        metadata = {
            "case_id": case["case_id"],
            "case_hash": case["case_hash"],
            "action": case["action"],
            "candidate_ids": tuple(case["candidate_ids"]),
            "schema_version": release["schema_version"],
            "evaluator_version": release["evaluator_version"],
            "evidence_hash": release["evidence_hash"],
        }
        with client.start_as_current_observation(name="phase063.frozen_case", as_type="evaluator", metadata=metadata) as observation:
            trace_id = getattr(observation, "trace_id", None)
            for name, passed in case["assertions"].items():
                client.create_score(name=f"phase063.{name}", value="PASS" if passed else "FAIL", trace_id=trace_id, data_type="CATEGORICAL")
    client.flush()
    after = path.read_bytes()
    if after != before:
        raise LangfusePublishError("release bytes changed during publish")
    return PublishResult(evidence_hash=str(release["evidence_hash"]), published_cases=len(release["cases"]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish-langfuse", action="store_true", help="explicitly mirror an already-complete safe release")
    parser.add_argument("--release", type=Path, default=Path(__file__).with_name("release.json"))
    arguments = parser.parse_args(argv)
    if not arguments.publish_langfuse:
        parser.error("--publish-langfuse is required; normal evaluation never contacts Langfuse")
    publish_release(arguments.release)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
