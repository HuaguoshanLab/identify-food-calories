"""Memory HTTP schemas and tenant-safe presentation tests without external providers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.auth.api import get_authenticated_principal
from app.agent.graph import NoopAgentRuntimeFactory
from app.main import create_app
from app.memory.api import get_memory_service
from app.memory.preferences import summarize_memory_preferences
from app.memory.service import MemorySyncPending, MemoryUnavailable
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

    def preference_summary(self, *, user_id: uuid.UUID):
        return summarize_memory_preferences([(item.category, item.canonical_text) for item in self.list_memories(user_id=user_id)])

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
    app.dependency_overrides[get_authenticated_principal] = lambda: principal
    app.dependency_overrides[get_memory_service] = lambda: service
    return TestClient(app)


def test_memory_api_openapi_and_dto_exclude_external_provider_fields() -> None:
    user_id = uuid.uuid4()
    memory = _memory(user_id=user_id)
    with _client(principal=user_id, service=StubMemoryService(memory)) as client:
        paths = client.app.openapi()["paths"]
        assert {"get", "post"} == set(paths["/api/v1/memories"])
        assert {"get", "patch", "delete"} <= set(paths["/api/v1/memories/{memory_id}"])
        listed = client.get("/api/v1/memories")
        detail = client.get(f"/api/v1/memories/{memory.id}")
        invalid = client.patch(f"/api/v1/memories/{memory.id}", json={"canonical_text": "不吃花生", "external_memory_id": "forged"})
    assert listed.status_code == 200 and "external_memory_id" not in listed.json()[0]
    assert detail.status_code == 200 and "external_memory_id" not in detail.json()
    assert invalid.status_code == 422


def test_memory_api_cross_user_updates_and_deletes_are_not_found() -> None:
    owner, other = uuid.uuid4(), uuid.uuid4()
    memory = _memory(user_id=owner)
    with _client(principal=other, service=StubMemoryService(memory)) as client:
        assert client.get(f"/api/v1/memories/{memory.id}").status_code == 404
        assert client.patch(f"/api/v1/memories/{memory.id}", json={"canonical_text": "不吃花生"}).status_code == 404
        assert client.delete(f"/api/v1/memories/{memory.id}").status_code == 404


def test_memory_api_returns_conflict_for_an_unresolved_cloud_write() -> None:
    class PendingService(StubMemoryService):
        def update_memory(self, **kwargs):
            raise MemorySyncPending()

    owner = uuid.uuid4()
    memory = _memory(user_id=owner)
    with _client(principal=owner, service=PendingService(memory)) as client:
        response = client.patch(f"/api/v1/memories/{memory.id}", json={"canonical_text": "不吃辣"})
    assert response.status_code == 409
    assert response.json() == {"detail": "记忆正在同步或同步结果尚未确认，请稍后重试。"}


def test_preference_summary_is_owner_scoped_read_only_and_splits_legacy_text() -> None:
    owner = uuid.uuid4()
    memory = _memory(user_id=owner)
    memory.canonical_text = "不吃辣 饮食清淡"
    service = StubMemoryService(memory)
    with _client(principal=owner, service=service) as client:
        response = client.get("/api/v1/memories/preference-summary")
        assert response.status_code == 200
        assert response.json() == {"exclusions": ["不吃辣"], "taste_preferences": ["清淡"]}
    with _client(principal=uuid.uuid4(), service=service) as client:
        assert client.get("/api/v1/memories/preference-summary").json() == {"exclusions": [], "taste_preferences": []}
    assert memory.canonical_text == "不吃辣 饮食清淡"
    assert memory.external_memory_id == "must-never-appear"
