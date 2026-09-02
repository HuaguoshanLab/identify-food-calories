"""Public admin API contracts, separate from SQLAlchemy audit state."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AdminProbeResponse(BaseModel):
    """Minimal backend-only proof that database RBAC granted access."""

    status: Literal["ADMIN_ACCESS_GRANTED"] = "ADMIN_ACCESS_GRANTED"


class AdminAuditEventResponse(BaseModel):
    """Allowlisted audit projection; it cannot grow into a raw event payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    actor_identifier: str
    occurred_at: datetime
    action: str
    object_type: str
    object_id: str
    reason: str
    before: dict[str, object]
    after: dict[str, object]
    related_version: str | None
    command_key: str


class AdminAuditPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: list[AdminAuditEventResponse]
    next_cursor: str | None


class AdminAuditQuery(BaseModel):
    """Bounded, read-only filters accepted by the audit timeline."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    limit: int = Field(default=50, ge=1, le=100)
    cursor: str | None = Field(default=None, min_length=16, max_length=500)
    action: str | None = Field(default=None, max_length=80)
    object_type: str | None = Field(default=None, max_length=80)
    object_id: str | None = Field(default=None, max_length=160)
    actor_identifier: str | None = Field(default=None, max_length=320)
    reason: str | None = Field(default=None, max_length=500)
    occurred_after: datetime | None = None
    occurred_before: datetime | None = None

    @field_validator("action", "object_type", "object_id", "actor_identifier", "reason")
    @classmethod
    def normalize_optional_filter(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("filter must not be blank")
        return normalized
