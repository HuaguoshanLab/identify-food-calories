"""HTTP translation for registration; business rules remain in RegistrationService."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth.repository import SqlAlchemyAuthRepository
from app.auth.schemas import (
    CodeDispatchAcceptedResponse,
    RegisterRequest,
    VerificationCodeRequest,
    VerificationPendingResponse,
    VerificationSuccessResponse,
)
from app.auth.service import (
    InvalidVerificationCode,
    RegistrationDispatch,
    RegistrationService,
    ResendCooldown,
    VerificationAttemptsExceeded,
    VerificationCodeExpired,
    VerificationContextInvalid,
)
from app.core.database import get_session
from app.notifications.smtp import create_smtp_mail_provider


REGISTRATION_CONTEXT_COOKIE = "registration_context"
router = APIRouter(prefix="/api/v1/auth/register", tags=["authentication"])


def get_registration_service(
    request: Request, session: Session = Depends(get_session)
) -> RegistrationService:
    """Compose ports at the HTTP boundary; the service never sees FastAPI dependencies."""

    settings = request.app.state.settings
    return RegistrationService(
        repository=SqlAlchemyAuthRepository(session),
        mail_provider=create_smtp_mail_provider(settings),
        secret_key=settings.secret_key.get_secret_value(),
        commit=session.commit,
        rollback=session.rollback,
    )


@router.post(
    "",
    response_model=CodeDispatchAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def register(
    payload: RegisterRequest,
    response: Response,
    request: Request,
    service: RegistrationService = Depends(get_registration_service),
) -> CodeDispatchAcceptedResponse:
    dispatch = service.register(email=payload.email, password=payload.password)
    _set_context_cookie(response=response, request=request, dispatch=dispatch)
    return _accepted(dispatch)


@router.get("/context", response_model=VerificationPendingResponse)
def registration_context(
    registration_context: str | None = Cookie(default=None),
    service: RegistrationService = Depends(get_registration_service),
) -> VerificationPendingResponse | JSONResponse:
    if not registration_context:
        return _error(
            status_code=status.HTTP_409_CONFLICT,
            code="VERIFICATION_CONTEXT_INVALID",
            message="验证信息已失效，请重新开始。",
        )
    try:
        return service.get_context(registration_context)
    except VerificationContextInvalid:
        return _error(
            status_code=status.HTTP_409_CONFLICT,
            code="VERIFICATION_CONTEXT_INVALID",
            message="验证信息已失效，请重新开始。",
        )


@router.post("/verify", response_model=VerificationSuccessResponse)
def verify_registration(
    payload: VerificationCodeRequest,
    response: Response,
    request: Request,
    registration_context: str | None = Cookie(default=None),
    service: RegistrationService = Depends(get_registration_service),
) -> VerificationSuccessResponse | JSONResponse:
    if not registration_context:
        return _error(
            status_code=status.HTTP_409_CONFLICT,
            code="VERIFICATION_CONTEXT_INVALID",
            message="验证信息已失效，请重新开始。",
        )
    try:
        service.verify(context_token=registration_context, code=payload.code)
    except InvalidVerificationCode:
        return _error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_VERIFICATION_CODE",
            message="验证码不正确，请重新输入。",
        )
    except VerificationCodeExpired:
        return _error(
            status_code=status.HTTP_410_GONE,
            code="VERIFICATION_CODE_EXPIRED",
            message="验证码已过期，请重新发送。",
        )
    except VerificationAttemptsExceeded:
        return _error(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="VERIFICATION_ATTEMPTS_EXCEEDED",
            message="验证码已失效，请重新发送后再试。",
        )
    except VerificationContextInvalid:
        return _error(
            status_code=status.HTTP_409_CONFLICT,
            code="VERIFICATION_CONTEXT_INVALID",
            message="验证信息已失效，请重新开始。",
        )

    response.delete_cookie(
        REGISTRATION_CONTEXT_COOKIE,
        path="/api/v1/auth/register",
        secure=request.app.state.settings.cookie_secure,
        httponly=True,
        samesite="strict",
    )
    return VerificationSuccessResponse()


@router.post(
    "/resend",
    response_model=CodeDispatchAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def resend_registration_code(
    response: Response,
    request: Request,
    registration_context: str | None = Cookie(default=None),
    service: RegistrationService = Depends(get_registration_service),
) -> CodeDispatchAcceptedResponse | JSONResponse:
    if not registration_context:
        return _error(
            status_code=status.HTTP_409_CONFLICT,
            code="VERIFICATION_CONTEXT_INVALID",
            message="验证信息已失效，请重新开始。",
        )
    try:
        dispatch = service.resend(registration_context)
    except ResendCooldown as error:
        return _error(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="RESEND_COOLDOWN",
            message="验证码暂时不能重发。",
            retry_after=error.retry_after,
        )
    except VerificationContextInvalid:
        return _error(
            status_code=status.HTTP_409_CONFLICT,
            code="VERIFICATION_CONTEXT_INVALID",
            message="验证信息已失效，请重新开始。",
        )
    _set_context_cookie(response=response, request=request, dispatch=dispatch)
    return _accepted(dispatch)


def _accepted(dispatch: RegistrationDispatch) -> CodeDispatchAcceptedResponse:
    return CodeDispatchAcceptedResponse(
        masked_email=dispatch.masked_email,
        resend_available_at=dispatch.resend_available_at,
        expires_at=dispatch.expires_at,
    )


def _set_context_cookie(
    *, response: Response, request: Request, dispatch: RegistrationDispatch
) -> None:
    settings = request.app.state.settings
    response.set_cookie(
        REGISTRATION_CONTEXT_COOKIE,
        dispatch.context_token,
        max_age=600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/api/v1/auth/register",
    )


def _error(
    *,
    status_code: int,
    code: str,
    message: str,
    retry_after: int | None = None,
) -> JSONResponse:
    error: dict[str, str | int] = {
        "code": code,
        "message": message,
        "request_id": str(uuid.uuid4()),
    }
    if retry_after is not None:
        error["retry_after"] = retry_after
    return JSONResponse(status_code=status_code, content={"error": error})
