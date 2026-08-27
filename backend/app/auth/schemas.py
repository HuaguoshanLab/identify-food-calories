"""Public runtime-validated authentication contracts, deliberately separate from ORM."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


EmailAddress = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=3,
        max_length=320,
        pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$",
    ),
]


class RegisterRequest(BaseModel):
    email: EmailAddress
    password: str = Field(min_length=12, max_length=128)


class VerificationCodeRequest(BaseModel):
    code: str = Field(pattern=r"^[0-9]{6}$")


class VerificationPendingResponse(BaseModel):
    masked_email: str
    resend_available_at: datetime
    expires_at: datetime


class PublicUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailAddress
    email_verified_at: datetime | None
    is_active: bool


class CurrentUserResponse(PublicUser):
    """Role is server-authored output; no public input schema accepts it."""

    role: str


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    device_label: str | None
