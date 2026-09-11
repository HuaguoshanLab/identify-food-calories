"""Contract tests for the optional, payload-free Langfuse release mirror."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from evals.phase_06_3.langfuse_publish import LangfusePublishError, publish_release
from evals.phase_06_3.langfuse_retention import (
    RetentionFailure,
    TraceRecord,
    purge_detailed_experiments,
)


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


class _FakeRetentionClient:
    def __init__(self, traces: list[TraceRecord], *, delayed_deletions: int = 0) -> None:
        self._traces = list(traces)
        self._delayed_deletions = delayed_deletions
        self._pending: set[str] = set()
        self.list_calls = 0
        self.deleted: list[tuple[str, ...]] = []

    def list_traces(self, *, cutoff_utc: datetime, page: int, limit: int) -> tuple[TraceRecord, ...]:
        del cutoff_utc
        self.list_calls += 1
        if self._pending and self.list_calls > self._delayed_deletions:
            self._traces = [trace for trace in self._traces if trace.trace_id not in self._pending]
            self._pending.clear()
        start = (page - 1) * limit
        return tuple(self._traces[start : start + limit])

    def delete_traces(self, trace_ids: tuple[str, ...]) -> None:
        self.deleted.append(trace_ids)
        self._pending.update(trace_ids)


def _trace(trace_id: str, *, days_old: int, now: datetime, action: str) -> TraceRecord:
    return TraceRecord(trace_id=trace_id, timestamp_utc=now - timedelta(days=days_old), action=action)


def test_retention_keeps_29_days_and_purges_30_days_or_older_for_pass_and_fail() -> None:
    now = datetime(2026, 9, 11, 12, tzinfo=UTC)
    client = _FakeRetentionClient(
        [
            _trace("29-pass", days_old=29, now=now, action="PASS"),
            _trace("30-pass", days_old=30, now=now, action="PASS"),
            _trace("30-fail", days_old=30, now=now, action="FAIL"),
            _trace("31-fail", days_old=31, now=now, action="FAIL"),
        ]
    )

    report = purge_detailed_experiments(
        client=client,
        now=lambda: now,
        page_size=2,
        batch_size=2,
        max_pages=8,
        max_attempts=3,
        deadline_seconds=1,
        sleep=lambda _seconds: None,
    )

    assert report.as_json() == {
        "cutoff_utc": "2026-08-12T12:00:00Z",
        "scanned": 4,
        "requested": 3,
        "verified_deleted": 3,
        "remaining_overdue": 0,
        "status": "PASS",
    }
    assert {trace_id for batch in client.deleted for trace_id in batch} == {"30-pass", "30-fail", "31-fail"}


def test_retention_paginates_and_requeries_asynchronous_deletions_without_writing_files() -> None:
    now = datetime(2026, 9, 11, tzinfo=UTC)
    client = _FakeRetentionClient(
        [_trace(f"old-{index}", days_old=31, now=now, action="PASS" if index % 2 else "FAIL") for index in range(5)],
        delayed_deletions=5,
    )

    report = purge_detailed_experiments(
        client=client,
        now=lambda: now,
        page_size=2,
        batch_size=2,
        max_pages=8,
        max_attempts=6,
        deadline_seconds=1,
        sleep=lambda _seconds: None,
    )

    assert report.requested == 5
    assert report.verified_deleted == 5
    assert report.status == "PASS"
    assert len(client.deleted) == 3


def test_retention_fails_closed_when_async_deletion_cannot_be_verified() -> None:
    now = datetime(2026, 9, 11, 12, tzinfo=UTC)
    client = _FakeRetentionClient([_trace("old", days_old=31, now=now, action="FAIL")], delayed_deletions=99)

    with pytest.raises(RetentionFailure, match="RETENTION_UNVERIFIED"):
        purge_detailed_experiments(
            client=client,
            now=lambda: now,
            page_size=2,
            batch_size=2,
            max_pages=8,
            max_attempts=2,
            deadline_seconds=1,
            sleep=lambda _seconds: None,
        )


def test_retention_rejects_pages_that_exceed_the_configured_bound() -> None:
    now = datetime(2026, 9, 11, 12, tzinfo=UTC)
    client = _FakeRetentionClient([_trace(f"old-{index}", days_old=31, now=now, action="PASS") for index in range(3)])

    with pytest.raises(RetentionFailure, match="RETENTION_PAGE_LIMIT"):
        purge_detailed_experiments(
            client=client,
            now=lambda: now,
            page_size=1,
            batch_size=1,
            max_pages=2,
            max_attempts=2,
            deadline_seconds=1,
            sleep=lambda _seconds: None,
        )
