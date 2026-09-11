"""Explicit, bounded 30-day cleanup for Phase 06.3's offline Langfuse mirror.

This command is intentionally not imported by application startup or a scheduler.
It only deletes old traces created by ``langfuse_publish.py``; Langfuse cascades that
deletion to the trace's observations and scores.  No payload is read, emitted, or
persisted: the sole result is a small JSON object written to stdout.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

import httpx


_TRACE_NAME = "phase063.frozen_case"
_RETENTION = timedelta(days=30)
_DEFAULT_PAGE_SIZE = 100
_DEFAULT_BATCH_SIZE = 50
_MAX_PAGES = 100
_MAX_ATTEMPTS = 10
_DEADLINE_SECONDS = 60.0


class RetentionFailure(RuntimeError):
    """A safe operational code; callers must not print underlying API details."""


@dataclass(frozen=True, slots=True)
class TraceRecord:
    """The only trace fields that cleanup is permitted to inspect."""

    trace_id: str
    timestamp_utc: datetime
    # Test-only observability proves PASS/FAIL is never a selection criterion.
    # The HTTP client intentionally does not populate this from remote metadata.
    action: str = "UNSPECIFIED"


class RetentionClient(Protocol):
    def list_traces(self, *, cutoff_utc: datetime, page: int, limit: int) -> tuple[TraceRecord, ...]: ...

    def delete_traces(self, trace_ids: tuple[str, ...]) -> None: ...


@dataclass(frozen=True, slots=True)
class RetentionReport:
    cutoff_utc: str
    scanned: int
    requested: int
    verified_deleted: int
    remaining_overdue: int
    status: str

    def as_json(self) -> dict[str, str | int]:
        # Keep stdout an exact, small contract rather than a future dumping ground.
        return asdict(self)


class HttpLangfuseRetentionClient:
    """Official v3 public trace API adapter for the pinned local Langfuse image."""

    def __init__(self, *, base_url: str, public_key: str, secret_key: str, timeout_seconds: float) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            auth=(public_key, secret_key),
            timeout=httpx.Timeout(timeout_seconds),
        )

    def close(self) -> None:
        self._client.close()

    def list_traces(self, *, cutoff_utc: datetime, page: int, limit: int) -> tuple[TraceRecord, ...]:
        try:
            response = self._client.get(
                "/api/public/traces",
                params={
                    "name": _TRACE_NAME,
                    "toTimestamp": _format_utc(cutoff_utc),
                    "orderBy": "timestamp.asc",
                    "page": page,
                    "limit": limit,
                },
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise RetentionFailure("RETENTION_LIST_FAILED") from error
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise RetentionFailure("RETENTION_LIST_INVALID")
        records: list[TraceRecord] = []
        for item in payload["data"]:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not isinstance(item.get("timestamp"), str):
                raise RetentionFailure("RETENTION_LIST_INVALID")
            records.append(TraceRecord(trace_id=item["id"], timestamp_utc=_parse_utc(item["timestamp"])))
        return tuple(records)

    def delete_traces(self, trace_ids: tuple[str, ...]) -> None:
        if not trace_ids:
            return
        try:
            response = self._client.request("DELETE", "/api/public/traces", json={"traceIds": list(trace_ids)})
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise RetentionFailure("RETENTION_DELETE_FAILED") from error


def _parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise RetentionFailure("RETENTION_LIST_INVALID") from error
    if parsed.tzinfo is None:
        raise RetentionFailure("RETENTION_LIST_INVALID")
    return parsed.astimezone(UTC)


def _format_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _scan_overdue(
    *, client: RetentionClient, cutoff_utc: datetime, page_size: int, max_pages: int, deadline: float
) -> tuple[TraceRecord, ...]:
    records: list[TraceRecord] = []
    # The legacy API documents `toTimestamp` as "before", while our contract is
    # inclusive at exactly 30 UTC days. Query one second past the cutoff and apply
    # the authoritative inclusive comparison locally; a returned fresh trace is
    # ignored, never deleted.
    query_until = cutoff_utc + timedelta(seconds=1)
    for page in range(1, max_pages + 1):
        _require_before(deadline)
        current = client.list_traces(cutoff_utc=query_until, page=page, limit=page_size)
        # Never trust remote filter semantics to widen the destructive predicate.
        records.extend(record for record in current if record.timestamp_utc <= cutoff_utc)
        if len(current) < page_size:
            return tuple(records)
    _require_before(deadline)
    raise RetentionFailure("RETENTION_PAGE_LIMIT")


def _require_before(deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise RetentionFailure("RETENTION_DEADLINE")


def purge_detailed_experiments(
    *,
    client: RetentionClient,
    now: Callable[[], datetime],
    page_size: int = _DEFAULT_PAGE_SIZE,
    batch_size: int = _DEFAULT_BATCH_SIZE,
    max_pages: int = _MAX_PAGES,
    max_attempts: int = _MAX_ATTEMPTS,
    deadline_seconds: float = _DEADLINE_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> RetentionReport:
    """Delete only `timestamp <= now_utc - 30d`, then requery until verified."""

    if min(page_size, batch_size, max_pages, max_attempts) <= 0 or deadline_seconds <= 0:
        raise ValueError("retention bounds must be positive")
    current = now()
    if current.tzinfo is None:
        raise ValueError("retention clock must be timezone-aware")
    cutoff = current.astimezone(UTC) - _RETENTION
    deadline = time.monotonic() + deadline_seconds
    selected = _scan_overdue(
        client=client, cutoff_utc=cutoff, page_size=page_size, max_pages=max_pages, deadline=deadline
    )
    requested_ids = tuple(dict.fromkeys(record.trace_id for record in selected))
    for index in range(0, len(requested_ids), batch_size):
        _require_before(deadline)
        client.delete_traces(requested_ids[index : index + batch_size])

    remaining: tuple[TraceRecord, ...] = selected
    for attempt in range(max_attempts):
        _require_before(deadline)
        remaining = _scan_overdue(
            client=client, cutoff_utc=cutoff, page_size=page_size, max_pages=max_pages, deadline=deadline
        )
        if not remaining:
            return RetentionReport(
                cutoff_utc=_format_utc(cutoff),
                scanned=len(selected),
                requested=len(requested_ids),
                verified_deleted=len(requested_ids),
                remaining_overdue=0,
                status="PASS",
            )
        if attempt + 1 < max_attempts:
            sleep(min(0.25 * (2**attempt), 2.0, max(deadline - time.monotonic(), 0.0)))
    # A non-empty response could be an asynchronous delay or a partial delete.
    # Neither is safe to report as success, and neither is persisted locally.
    raise RetentionFailure("RETENTION_UNVERIFIED")


def _client_from_environment() -> HttpLangfuseRetentionClient:
    base_url = os.environ.get("LANGFUSE_HOST") or os.environ.get("LANGFUSE_BASE_URL")
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
    if not base_url or not public_key or not secret_key:
        raise RetentionFailure("RETENTION_CONFIG_MISSING")
    return HttpLangfuseRetentionClient(
        base_url=base_url,
        public_key=public_key,
        secret_key=secret_key,
        timeout_seconds=min(_DEADLINE_SECONDS, 10.0),
    )


def main(
    argv: list[str] | None = None,
    *,
    client_factory: Callable[[], RetentionClient] | None = None,
    now: Callable[[], datetime] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    purge = subcommands.add_parser("purge", help="delete and verify expired Phase 06.3 experiment traces")
    purge.add_argument("--older-than", required=True, choices=("30d",))
    purge.add_argument("--verify", action="store_true", required=True)
    purge.add_argument("--format", required=True, choices=("json",))
    arguments = parser.parse_args(argv)
    if arguments.command != "purge":  # pragma: no cover - argparse owns this boundary.
        parser.error("purge is required")
    client: RetentionClient | None = None
    try:
        client = client_factory() if client_factory is not None else _client_from_environment()
        report = purge_detailed_experiments(client=client, now=now or (lambda: datetime.now(UTC)), sleep=sleep)
    except RetentionFailure as error:
        # Error details may contain hostnames or server responses. Keep stderr a code.
        print(str(error), file=sys.stderr)
        return 1
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()
    print(json.dumps(report.as_json(), separators=(",", ":"), sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
