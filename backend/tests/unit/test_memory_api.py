"""Memory HTTP schemas and tenant-safe presentation tests without external providers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.agent.api import get_agent_principal
from app.agent.graph import NoopAgentRuntimeFactory
from app.main import create_app
from app.memory.api import get_memory_service
from app.memory.service import MemoryUnavailable
from app.records.models import PreferenceMemoryLedger


NOW = datetime(2026, 8, 31, 8, 0, tzinfo=UTC)


def _memory(*, user_id: uuid.UUID) -> PreferenceMemoryLedger:
    return PreferenceMemoryLedger(id=uuid.uuid4(), user_id=user_id, category="avoidance", source_kind="user_statement", canonical_text="不吃花生", external_memory_id="must-never-appear", is_active=True, created_at=NOW, updated_at=NOW, deleted_at=None)


class StubMemoryService:
    def __init__(self, memory: PreferenceMemoryLedger) -> None:
        self.memory = memory

    def create_direct(self, *, user_id: uuid.UUID, category: str, canonical_text: str) -> PreferenceMemoryLedger:
        return self.memory

    def confirm_inference(self, *, memory_id: uuid.UUID, user_id: uuid.UUID) -> PreferenceMemoryLedger:
        return self.get_memory(memory_id=memory_id, user_id=user_id)

    def list_memories(self, *, user_id: uuid.UUID) -> list[PreferenceMemoryLedger]:
        return [self.memory] if user_id == self.memory.user_id else []

    def get_memory(self, *, memory_id: uuid.UUID, user_id: uuid.UUID) -> PreferenceMemoryLedger:
        if memory_id != self.memory.id or user_id != self.memory.user_id:
            raise MemoryUnavailable()
        return self.memory

    def update_memory(self, *, memory_id: uuid.UUID, user_id: uuid.UUID, canonical_text: str) -> PreferenceMemoryLedger:
        memory = self.get_memory(memory_id=memory_id, user_id=user_id)
        memory.source_kind = "user_maintained"
        return memory

    def delete_memory(self, *, memory_id: uuid.UUID, user_id: uuid.UUID) -> None:
        self.get_memory(memory_id=memory_id, user_id=user_id)


def _client(*, principal: uuid.UUID, service: StubMemoryService) -> TestClient:
    app = create_app(runtime_factory=NoopAgentRuntimeFactory())
    app.dependency_overrides[get_agent_principal] = lambda: principal
    app.dependency_overrides[get_memory_service] = lambda: service
    return TestClient(app)


def test_memory_api_openapi_and_dto_exclude_external_provider_fields() -> None:
    user_id = uuid.uuid4()
    memory = _memory(user_id=user_id)
    with _client(principal=user_id, service=StubMemoryService(memory)) as client:
        paths = client.app.openapi()["paths"]
        assert {"get", "post"} == set(paths["/api/v1/memories"])
        assert {"patch", "delete"} <= set(paths["/api/v1/memories/{memory_id}"])
        listed = client.get("/api/v1/memories")
        invalid = client.patch(f"/api/v1/memories/{memory.id}", json={"canonical_text": "不吃花生", "external_memory_id": "forged"})
    assert listed.status_code == 200 and "external_memory_id" not in listed.json()[0]
    assert invalid.status_code == 422


def test_memory_api_cross_user_updates_and_deletes_are_not_found() -> None:
    owner, other = uuid.uuid4(), uuid.uuid4()
    memory = _memory(user_id=owner)
    with _client(principal=other, service=StubMemoryService(memory)) as client:
        assert client.patch(f"/api/v1/memories/{memory.id}", json={"canonical_text": "不吃花生"}).status_code == 404
        assert client.delete(f"/api/v1/memories/{memory.id}").status_code == 404
