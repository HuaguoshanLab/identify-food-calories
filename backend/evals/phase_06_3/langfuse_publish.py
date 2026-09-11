"""Explicit, payload-free mirror for an already-complete Phase 06.3 release.

This module is deliberately outside the application runtime.  Phoenix remains the
only online tracing path; importing this file does not import the Langfuse SDK or
read its credentials.  The optional CLI validates a synthetic, hash-bound report
before it creates a Langfuse client and exports a deliberately smaller projection.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from evals.phase_06_3.evaluate import EvaluationContractError, validate_release


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


def _load_safe_release(path: Path) -> dict[str, object]:
    """Share the evaluator's source-bound contract before any client is created."""
    try:
        payload = validate_release(path, require_pass=False)
    except EvaluationContractError as error:
        raise LangfusePublishError("release does not satisfy the strict frozen allowlist contract") from error
    return payload


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
            "release_decision": release["decision"],
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
