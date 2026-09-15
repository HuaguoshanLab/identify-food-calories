"""Safe public memory-management schemas with no provider IDs or scores."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


MemoryCategory = Literal["goal", "avoidance", "stable_preference"]


class MemoryCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: MemoryCategory
    canonical_text: str = Field(min_length=1, max_length=1000)


class MemoryUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_text: str = Field(min_length=1, max_length=1000)


class MemoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    category: MemoryCategory
    source_kind: Literal["user_statement", "model_inference", "user_maintained"]
    canonical_text: str
    created_at: datetime
    updated_at: datetime


class MemoryPreferenceSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    exclusions: tuple[str, ...]
    taste_preferences: tuple[str, ...]
