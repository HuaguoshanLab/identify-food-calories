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
