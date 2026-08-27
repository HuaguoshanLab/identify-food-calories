"""Public runtime-validated authentication contracts, deliberately separate from ORM."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

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


class LoginRequest(BaseModel):
    email: EmailAddress
    password: str = Field(min_length=12, max_length=128)


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(gt=0)


class VerificationCodeRequest(BaseModel):
    code: str = Field(pattern=r"^[0-9]{6}$")


class VerificationPendingResponse(BaseModel):
    masked_email: str
    resend_available_at: datetime
    expires_at: datetime


class CodeDispatchAcceptedResponse(VerificationPendingResponse):
    status: Literal["CODE_DISPATCH_ACCEPTED"] = "CODE_DISPATCH_ACCEPTED"


class VerificationSuccessResponse(BaseModel):
    status: Literal["EMAIL_VERIFIED"] = "EMAIL_VERIFIED"
    message: Literal["邮箱验证成功，请登录。"] = "邮箱验证成功，请登录。"
    next_action: Literal["login"] = "login"


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
