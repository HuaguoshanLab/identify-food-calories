"""Safe source-tagged retrieval contracts."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol


ContextSource = Literal["preference", "meal_history", "nutrition_knowledge"]


@dataclass(frozen=True, slots=True)
class RetrievedContextItem:
    source: ContextSource
    summary: str
    occurred_at: datetime | None = None


class RetrievalRepository(Protocol):
    def list_personal_history(self, *, user_id: uuid.UUID, query: str, limit: int) -> list[RetrievedContextItem]: ...
    def list_nutrition_knowledge(self, *, query: str, catalog_version: str | None, limit: int) -> list[RetrievedContextItem]: ...
