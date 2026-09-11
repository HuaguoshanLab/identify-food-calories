"""Contract tests for the optional, payload-free Langfuse release mirror."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from evals.phase_06_3.langfuse_publish import LangfusePublishError, publish_release


RELEASE = Path(__file__).parents[2] / "evals" / "phase_06_3" / "release.json"


class _FakeObservation:
    def __init__(self) -> None:
        self.updates: list[dict[str, object]] = []

    def __enter__(self) -> _FakeObservation:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def update(self, **payload: object) -> None:
        self.updates.append(payload)


class _FakeLangfuse:
    def __init__(self) -> None:
        self.observations: list[tuple[dict[str, object], _FakeObservation]] = []
        self.scores: list[dict[str, object]] = []
        self.flushed = False

    def start_as_current_observation(self, **payload: object) -> _FakeObservation:
        observation = _FakeObservation()
        self.observations.append((payload, observation))
        return observation

    def create_score(self, **payload: object) -> None:
        self.scores.append(payload)

    def flush(self) -> None:
        self.flushed = True


def _release_copy(tmp_path: Path) -> Path:
    destination = tmp_path / "release.json"
    destination.write_bytes(RELEASE.read_bytes())
    return destination


def _all_values(value: object) -> list[str]:
    if isinstance(value, dict):
        return [*map(str, value.keys()), *[item for nested in value.values() for item in _all_values(nested)]]
    if isinstance(value, list | tuple):
        return [item for nested in value for item in _all_values(nested)]
    return [str(value)]


def test_publish_mirrors_pass_and_fail_cases_with_only_safe_projection(tmp_path: Path) -> None:
    release = _release_copy(tmp_path)
    payload = json.loads(release.read_text(encoding="utf-8"))
    payload["cases"][0]["action"] = "FAIL"
    evidence = {key: value for key, value in payload.items() if key != "evidence_hash"}
    payload["evidence_hash"] = hashlib.sha256(
        json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    release.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    original = release.read_bytes()
    client = _FakeLangfuse()

    result = publish_release(release, client_factory=lambda: client)

    assert result.published_cases == 24
    assert client.flushed is True
    assert len(client.observations) == 24
    assert len(client.scores) == 24 * 5
    assert {"PASS", "FAIL"} <= {payload["metadata"]["action"] for payload, _ in client.observations}
    exported = _all_values(client.observations) + _all_values(client.scores)
    # Safe aggregate score names may contain words such as ``meal_graph``; this
    # assertion instead proves no human payload from the frozen report leaks.
    forbidden_payload = ("米饭", "番茄炒蛋", "must-not-export", "image-data", "secret-value")
    assert not any(part in value for part in forbidden_payload for value in exported)
    assert release.read_bytes() == original
    assert result.evidence_hash == payload["evidence_hash"]


@pytest.mark.parametrize(
    "field",
    [
        "query", "candidate_text", "user_id", "meal_body", "health_goal", "image",
        "base64", "prompt", "provider_response", "vector", "secret", "thought", "unknown",
    ],
)
def test_publish_rejects_sensitive_or_unknown_fields_before_client_creation(tmp_path: Path, field: str) -> None:
    release = _release_copy(tmp_path)
    payload = json.loads(release.read_text(encoding="utf-8"))
    payload["cases"][0][field] = "must-not-export"
    release.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    called = False

    def factory() -> _FakeLangfuse:
        nonlocal called
        called = True
        return _FakeLangfuse()

    with pytest.raises(LangfusePublishError, match="allowlist"):
        publish_release(release, client_factory=factory)

    assert called is False


def test_publish_rejects_non_pass_release_and_preserves_report_bytes(tmp_path: Path) -> None:
    release = _release_copy(tmp_path)
    payload = json.loads(release.read_text(encoding="utf-8"))
    payload["decision"] = "FAIL"
    release.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    original = release.read_bytes()

    with pytest.raises(LangfusePublishError, match="completed PASS"):
        publish_release(release, client_factory=_FakeLangfuse)

    assert release.read_bytes() == original
