"""Exercise the installed Mem0 SDK against an in-process HTTP transport."""

import json
import uuid

import httpx

from app.memory.providers import Mem0MemoryProvider


def test_hosted_sdk_wire_contract_preserves_user_scope_and_request_key(monkeypatch):
    monkeypatch.setenv("MEM0_TELEMETRY", "false")
    import mem0.client.main as sdk

    monkeypatch.setattr(sdk, "capture_client_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(sdk, "_maybe_alias_anon_to_email", lambda *args: None)
    user_id = uuid.uuid4()
    request_key = "a" * 64
    record = {"id": str(uuid.uuid4()), "user_id": str(user_id), "memory": "不吃辣",
              "metadata": {"request_key": request_key}}
    seen = []

    def handle(request):
        payload = json.loads(request.content) if request.content else {}
        seen.append((request.method, request.url.path, payload))
        if request.url.path == "/v1/ping/":
            return httpx.Response(200, json={"org_id": "test-org", "project_id": "test-project"})
        if request.method == "PUT":
            assert payload == {"text": "不吃辣 饮食清淡"}
            record["memory"] = payload["text"]
            return httpx.Response(200, json={"message": "updated"})
        if request.method == "DELETE":
            return httpx.Response(200, json={"message": "deleted"})
        if request.url.path == "/v3/memories/add/":
            assert payload["infer"] is False
            assert payload["user_id"] == str(user_id)
        elif request.url.path == "/v3/memories/":
            assert payload["filters"] == {"user_id": str(user_id), "metadata": {"request_key": request_key}}
            assert request.url.params["page_size"] == "2"
        elif request.url.path == "/v3/memories/search/":
            assert payload["filters"] == {"user_id": str(user_id)}
            assert payload["top_k"] == 3
            assert "user_id" not in payload
        else:
            raise AssertionError(request.url.path)
        return httpx.Response(200, json={"results": [record]})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        provider = object.__new__(Mem0MemoryProvider)
        provider._client = sdk.MemoryClient(api_key="unit-test-key", client=client)
        assert provider.create_direct(user_id=user_id, category="avoidance", canonical_text="不吃辣", request_key=request_key) == record["id"]
        assert provider.create(user_id=user_id, category="avoidance", canonical_text="不吃辣") == record["id"]
        provider.update(user_id=user_id, external_id=record["id"], category="avoidance", canonical_text="不吃辣 饮食清淡")
        assert provider.resolve_direct_by_request_key(user_id=user_id, request_key=request_key) == record["id"]
        assert provider.search(user_id=user_id, query="饮食偏好", limit=3)[0].canonical_text == "不吃辣 饮食清淡"
        provider.delete(user_id=user_id, external_id=record["id"])
    assert len(seen) == 7
