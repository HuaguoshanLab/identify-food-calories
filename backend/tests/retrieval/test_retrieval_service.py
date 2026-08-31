"""Pure service tests for source-separated safe context retrieval."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.records.models import PreferenceMemoryLedger
from app.retrieval.ports import RetrievedContextItem
from app.retrieval.service import PersonalContextService


NOW = datetime(2026, 8, 31, 8, 0, tzinfo=UTC)


class FakeMemoryService:
    def __init__(self, memories: list[PreferenceMemoryLedger]) -> None:
        self.memories = memories
        self.update_called = False

    def list_memories(self, *, user_id: uuid.UUID) -> list[PreferenceMemoryLedger]:
        return [memory for memory in self.memories if memory.user_id == user_id and memory.is_active and memory.deleted_at is None]

    def update_memory(self, **_kwargs: object) -> None:
        self.update_called = True


class FakeRetrievalRepository:
    def list_personal_history(self, *, user_id: uuid.UUID, query: str, limit: int) -> list[RetrievedContextItem]:
        assert query == "花生"
        return [RetrievedContextItem(source="meal_history", summary="历史记录：吃过花生", occurred_at=NOW)]

    def list_nutrition_knowledge(self, *, query: str, catalog_version: str | None, limit: int) -> list[RetrievedContextItem]:
        return [RetrievedContextItem(source="nutrition_knowledge", summary="受控营养知识：花生每百克数据")]


def test_current_avoidance_precedes_history_and_retrieval_never_edits_memory() -> None:
    user_id = uuid.uuid4()
    memory = PreferenceMemoryLedger(id=uuid.uuid4(), user_id=user_id, category="avoidance", source_kind="user_statement", canonical_text="不吃花生", external_memory_id="fake", is_active=True, created_at=NOW, updated_at=NOW, deleted_at=None)
    memories = FakeMemoryService([memory])
    result = PersonalContextService(memory_service=memories, repository=FakeRetrievalRepository()).retrieve(user_id=user_id, query="花生")
    assert [item.source for item in result] == ["preference", "meal_history", "nutrition_knowledge"]
    assert result[0].summary == "已参考你的忌口：不吃花生"
    assert memories.update_called is False
    assert all(not hasattr(item, "score") and not hasattr(item, "external_id") for item in result)
