"""Public Agent API contract before the runtime implementation arrives."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_all_agent_operations_require_authentication_without_starting_a_database_runtime() -> None:
    """The frozen public surface never exposes an anonymous Agent operation."""

    from app.agent.graph import NoopAgentRuntimeFactory

    app = create_app(runtime_factory=NoopAgentRuntimeFactory())
    thread_id = "00000000-0000-0000-0000-000000000001"
    calls = [
        ("post", "/api/v1/agent/threads", {"json": {"input_text": "米饭 100 克"}}),
        (
            "post",
            f"/api/v1/agent/threads/{thread_id}/input",
            {"json": {"kind": "description", "text": "米饭 100 克"}},
        ),
        ("get", f"/api/v1/agent/threads/{thread_id}", {}),
        ("get", f"/api/v1/agent/threads/{thread_id}/events", {}),
        ("post", f"/api/v1/agent/threads/{thread_id}/retry", {}),
        ("delete", f"/api/v1/agent/threads/{thread_id}", {}),
    ]

    with TestClient(app) as client:
        responses = [client.request(method, path, **kwargs) for method, path, kwargs in calls]

    assert all(response.status_code == 401 for response in responses)

    openapi = app.openapi()
    operation_ids = {
        operation.get("operationId")
        for path_item in openapi["paths"].values()
        for operation in path_item.values()
        if isinstance(operation, dict)
    }
    assert {
        "createAgentThread",
        "submitAgentInput",
        "getAgentThread",
        "streamAgentEvents",
        "retryAgentRun",
        "deleteAgentThread",
    } <= operation_ids


def test_reused_waiting_adjustment_does_not_resume_a_newer_checkpoint(monkeypatch):
    """The create-or-reuse lock may observe a completion after the initial lookup."""
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock
    from uuid import uuid4
    from app.agent import api
    from app.agent.schemas import AgentInputRequest

    execute = AsyncMock()
    monkeypatch.setattr(api, "_execute", execute)
    for state in ("running", "waiting_input", "completed", "failed", "limit_reached"):
        run = SimpleNamespace(status=state)
        service = SimpleNamespace(create_or_reuse_run=Mock(return_value=run))
        response = asyncio.run(api._submit_agent_input_after_admission(
            thread_id=uuid4(), payload=AgentInputRequest(kind="description", text="午餐换一份"),
            principal=uuid4(), service=service, runtime=SimpleNamespace(), latest=run,
            planning_thread=True, resume_payload={"feedback": "午餐换一份"}, planning_key="submission",
        ))
        assert response.status == api._status(state)
    execute.assert_not_called()
