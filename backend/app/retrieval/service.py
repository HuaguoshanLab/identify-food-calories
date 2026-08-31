"""Combine source-separated context without making retrieval a nutrition authority."""

from __future__ import annotations

import uuid

from app.memory.service import MemoryService
from app.retrieval.ports import RetrievedContextItem, RetrievalRepository


class PersonalContextService:
    """Current active preferences are first-class constraints, not inferences from old meals."""

    def __init__(self, *, memory_service: MemoryService, repository: RetrievalRepository) -> None:
        self._memory_service = memory_service
        self._repository = repository

    def retrieve(self, *, user_id: uuid.UUID, query: str, catalog_version: str | None = None) -> list[RetrievedContextItem]:
        preferences = [
            RetrievedContextItem(source="preference", summary=f"已参考你的{_category_label(memory.category)}：{memory.canonical_text}")
            for memory in self._memory_service.list_memories(user_id=user_id)
        ]
        # Preferences intentionally precede behaviour history: a new avoidance remains binding
        # even if old records show the user previously ate that food.
        return preferences + self._repository.list_personal_history(user_id=user_id, query=query, limit=3) + self._repository.list_nutrition_knowledge(query=query, catalog_version=catalog_version, limit=3)


def _category_label(category: str) -> str:
    return {"goal": "目标", "avoidance": "忌口", "stable_preference": "偏好"}[category]
