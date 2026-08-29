"""Public Agent API contract before the runtime implementation arrives."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.main import create_app


def test_all_agent_operations_require_authentication_and_return_one_sentinel() -> None:
    """The predeclared surface must not accidentally expose an anonymous stub."""

    from app.agent.api import get_agent_principal

    app = create_app()
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
        assert client.post("/api/v1/agent/threads", json={"input_text": "米饭"}).status_code == 401

        app.dependency_overrides[get_agent_principal] = lambda: uuid.UUID(int=1)
        responses = [client.request(method, path, **kwargs) for method, path, kwargs in calls]

    assert all(response.status_code == 501 for response in responses)
    assert all(response.json()["error"]["code"] == "AGENT_NOT_IMPLEMENTED" for response in responses)

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
