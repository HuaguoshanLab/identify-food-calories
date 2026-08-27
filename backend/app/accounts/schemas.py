"""Runtime-validated public contracts for account recovery HTTP endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.auth.schemas import EmailAddress, VerificationCodeRequest


class ForgotPasswordRequest(BaseModel):
    email: EmailAddress


class ResetPasswordRequest(VerificationCodeRequest):
    new_password: str = Field(min_length=12, max_length=128)


class RecoveryPendingResponse(BaseModel):
    masked_email: str
    resend_available_at: datetime
    expires_at: datetime


class RecoveryDispatchAcceptedResponse(RecoveryPendingResponse):
    status: Literal["RECOVERY_CODE_DISPATCH_ACCEPTED"] = "RECOVERY_CODE_DISPATCH_ACCEPTED"


class RecoveryCodeVerifiedResponse(BaseModel):
    status: Literal["RECOVERY_CODE_VERIFIED"] = "RECOVERY_CODE_VERIFIED"


class PasswordResetResponse(BaseModel):
    status: Literal["PASSWORD_RESET"] = "PASSWORD_RESET"
    message: Literal["密码已更新，请重新登录。"] = "密码已更新，请重新登录。"
