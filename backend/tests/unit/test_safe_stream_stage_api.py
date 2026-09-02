"""Public SSE stage contract: only the versioned allowlist reaches browsers."""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.agent.api import _safe_stream_event


@dataclass(frozen=True)
class _PersistedEvent:
    event_type: str
    safe_summary: str
    payload: dict[str, object]


def test_sse_serializes_only_the_versioned_safe_stage_allowlist() -> None:
    event = _PersistedEvent(
        event_type="tool_calculation",
        safe_summary="正在通过受控工具计算营养信息。",
        payload={
            "node": "calculate_nutrition",
            "reasoning": "private chain of thought",
            "provider_body": {"image_base64": "secret-image"},
            "state": {"messages": ["private input"]},
        },
    )

    body = _safe_stream_event(event)

    assert body is not None
    document = json.loads(body)
    assert document == {
        "schema_version": "safe-stream-stage.v1",
        "stage": "tool_calculation",
        "message": "正在通过受控工具计算营养信息。",
    }
    assert all(forbidden not in body for forbidden in ("node", "reasoning", "provider", "base64", "state", "private"))


def test_sse_rejects_unknown_or_unvalidated_completion_events() -> None:
    assert _safe_stream_event(_PersistedEvent("unknown-node", "ignored", {})) is None
    assert _safe_stream_event(_PersistedEvent("completed", "ignored", {})) is None
    completed = _safe_stream_event(
        _PersistedEvent("completed_validated", "校验完成，结果已准备好。", {})
    )
    assert completed is not None
    assert json.loads(completed)["stage"] == "completed"
