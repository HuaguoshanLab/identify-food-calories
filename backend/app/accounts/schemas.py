"""Runtime-validated public contracts for account recovery HTTP endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.auth.schemas import EmailAddress, VerificationCodeRequest


class ForgotPasswordRequest(BaseModel):
    email: EmailAddress


class ResetPasswordRequest(VerificationCodeRequest):
    new_password: str = Field(min_length=12, max_length=128)


class RecoveryPendingResponse(BaseModel):
    """Fixed pending shape; account-derived fields would become an enumeration oracle."""

    status: Literal["RECOVERY_PENDING"] = "RECOVERY_PENDING"


class RecoveryDispatchAcceptedResponse(BaseModel):
    """A fixed 202 envelope so reset initiation cannot enumerate accounts."""

    status: Literal["RECOVERY_CODE_DISPATCH_ACCEPTED"] = "RECOVERY_CODE_DISPATCH_ACCEPTED"


class RecoveryCodeVerifiedResponse(BaseModel):
    status: Literal["RECOVERY_CODE_VERIFIED"] = "RECOVERY_CODE_VERIFIED"


class PasswordResetResponse(BaseModel):
    status: Literal["PASSWORD_RESET"] = "PASSWORD_RESET"
    message: Literal["密码已更新，请重新登录。"] = "密码已更新，请重新登录。"
