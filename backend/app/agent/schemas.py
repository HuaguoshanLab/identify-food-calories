"""HTTP-only Agent request and response schemas.

These models deliberately do not expose the ORM ledger, LangGraph state or
provider payloads.  The public API stays stable while those implementation
details evolve behind the service boundary.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field
from app.planning.schemas import PlanningProfileInput, PreferenceReview


class AgentThreadStatus(StrEnum):
    """All lifecycle states that browser clients must handle from day one."""

    WAITING = "waiting"
    PARTIAL = "partial"
    COMPLETED = "completed"
    RETRYABLE = "retryable"
    TERMINAL = "terminal"
    DELETION_PENDING = "deletion_pending"


class AgentInputKind(StrEnum):
    DESCRIPTION = "description"


class AgentThreadCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_text: str = Field(min_length=1, max_length=4_000)


class DietPlanningStartCommand(BaseModel):
    """The complete transient input for a new plan; profiles are never inferred by a model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile: PlanningProfileInput
    preferences: PreferenceReview
    save_profile: bool = False


class AgentInputRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: AgentInputKind
    text: str = Field(min_length=1, max_length=4_000)


class AgentThreadSnapshot(BaseModel):
    """Safe, implementation-independent thread shape reserved for future GREEN."""

    model_config = ConfigDict(extra="forbid")

    thread_id: uuid.UUID
    status: AgentThreadStatus
    revision: int = Field(ge=0)
    report: dict[str, object] | None = None
    recovery_code: str | None = Field(default=None, min_length=1, max_length=80)


class AgentCommandAcceptedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thread_id: uuid.UUID
    status: AgentThreadStatus


class AgentImageAcceptedResponse(AgentCommandAcceptedResponse):
    """Public upload result exposes only opaque IDs and lifecycle state."""

    image_id: uuid.UUID


class AgentDeletionAcceptedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thread_id: uuid.UUID
    status: AgentThreadStatus = AgentThreadStatus.DELETION_PENDING
    due_at: datetime


class AgentErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    request_id: uuid.UUID


class AgentErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: AgentErrorDetail
