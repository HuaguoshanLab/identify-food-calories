"""HTTP translation for password recovery; recovery secrets stay in an HttpOnly cookie."""

from __future__ import annotations

from app.core.logging import current_request_id

from urllib.parse import urlsplit

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.accounts.repository import SqlAlchemyAccountRecoveryRepository
from app.accounts.schemas import (
    ForgotPasswordRequest,
    PasswordResetResponse,
    RecoveryCodeVerifiedResponse,
    RecoveryDispatchAcceptedResponse,
    RecoveryPendingResponse,
    ResetPasswordRequest,
)
from app.accounts.service import (
    InvalidRecoveryCode,
    RecoveryAttemptsExceeded,
    RecoveryCodeExpired,
    RecoveryContextInvalid,
    RecoveryDispatch,
    RecoveryService,
    ResendCooldown,
)
from app.auth.schemas import VerificationCodeRequest
from app.core.database import get_session
from app.notifications.smtp import create_smtp_mail_provider


RECOVERY_CONTEXT_COOKIE = "password_recovery_context"
RECOVERY_CONTEXT_PATH = "/api/v1/auth/password-recovery"
router = APIRouter(prefix=RECOVERY_CONTEXT_PATH, tags=["account recovery"])


def get_recovery_service(
    request: Request, session: Session = Depends(get_session)
) -> RecoveryService:
    """Compose recovery ports using one request session for the complete transaction."""

    settings = request.app.state.settings
    repository = SqlAlchemyAccountRecoveryRepository(session)
    return RecoveryService(
        repository=repository,
        session_family_revoker=repository,
        mail_provider=create_smtp_mail_provider(settings),
        secret_key=settings.secret_key.get_secret_value(),
        commit=session.commit,
        rollback=session.rollback,
    )


@router.post(
    "/forgot",
    response_model=RecoveryDispatchAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def forgot_password(
    payload: ForgotPasswordRequest,
    response: Response,
    request: Request,
    service: RecoveryService = Depends(get_recovery_service),
) -> RecoveryDispatchAcceptedResponse | JSONResponse:
    if not _request_origin_is_allowed(request):
        return _csrf_error()
    dispatch = service.request_reset(email=payload.email)
    _set_context_cookie(response=response, request=request, dispatch=dispatch)
    # No account-derived fields leave this endpoint. Equal 202 envelopes and cookies
    # prevent attackers from using the recovery start as an account oracle.
    return RecoveryDispatchAcceptedResponse()


@router.get("/context", response_model=RecoveryPendingResponse)
def recovery_context(
    password_recovery_context: str | None = Cookie(default=None),
    service: RecoveryService = Depends(get_recovery_service),
) -> RecoveryPendingResponse | JSONResponse:
    if not password_recovery_context:
        return _context_invalid()
    try:
        return service.get_context(password_recovery_context)
    except RecoveryContextInvalid:
        return _context_invalid()


@router.post("/verify", response_model=RecoveryCodeVerifiedResponse)
def verify_recovery_code(
    payload: VerificationCodeRequest,
    request: Request,
    password_recovery_context: str | None = Cookie(default=None),
    service: RecoveryService = Depends(get_recovery_service),
) -> RecoveryCodeVerifiedResponse | JSONResponse:
    if not _request_origin_is_allowed(request):
        return _csrf_error()
    if not password_recovery_context:
        return _context_invalid()
    try:
        service.verify(context_token=password_recovery_context, code=payload.code)
    except InvalidRecoveryCode:
        return _error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_RECOVERY_CODE",
            message="验证码不正确，请重新输入。",
        )
    except RecoveryCodeExpired:
        return _error(
            status_code=status.HTTP_410_GONE,
            code="RECOVERY_CODE_EXPIRED",
            message="验证码已过期，请重新发送。",
        )
    except RecoveryAttemptsExceeded:
        return _error(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="RECOVERY_ATTEMPTS_EXCEEDED",
            message="验证码已失效，请重新发送后再试。",
        )
    except RecoveryContextInvalid:
        return _context_invalid()
    return RecoveryCodeVerifiedResponse()


@router.post(
    "/resend",
    response_model=RecoveryDispatchAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def resend_recovery_code(
    response: Response,
    request: Request,
    password_recovery_context: str | None = Cookie(default=None),
    service: RecoveryService = Depends(get_recovery_service),
) -> RecoveryDispatchAcceptedResponse | JSONResponse:
    if not _request_origin_is_allowed(request):
        return _csrf_error()
    if not password_recovery_context:
        return _context_invalid()
    try:
        dispatch = service.resend(password_recovery_context)
    except ResendCooldown as error:
        return _error(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="RESEND_COOLDOWN",
            message="验证码暂时不能重发。",
            retry_after=error.retry_after,
        )
    except RecoveryContextInvalid:
        return _context_invalid()
    _set_context_cookie(response=response, request=request, dispatch=dispatch)
    return RecoveryDispatchAcceptedResponse()


@router.post("/reset", response_model=PasswordResetResponse)
def reset_password(
    payload: ResetPasswordRequest,
    response: Response,
    request: Request,
    password_recovery_context: str | None = Cookie(default=None),
    service: RecoveryService = Depends(get_recovery_service),
) -> PasswordResetResponse | JSONResponse:
    if not _request_origin_is_allowed(request):
        return _csrf_error()
    if not password_recovery_context:
        return _context_invalid()
    try:
        service.reset(
            context_token=password_recovery_context,
            code=payload.code,
            new_password=payload.new_password,
        )
    except InvalidRecoveryCode:
        return _error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_RECOVERY_CODE",
            message="验证码不正确，请重新输入。",
        )
    except RecoveryCodeExpired:
        return _error(
            status_code=status.HTTP_410_GONE,
            code="RECOVERY_CODE_EXPIRED",
            message="验证码已过期，请重新发送。",
        )
    except RecoveryAttemptsExceeded:
        return _error(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="RECOVERY_ATTEMPTS_EXCEEDED",
            message="验证码已失效，请重新发送后再试。",
        )
    except RecoveryContextInvalid:
        return _context_invalid()
    _clear_context_cookie(response=response, request=request)
    return PasswordResetResponse()


def _set_context_cookie(
    *, response: Response, request: Request, dispatch: RecoveryDispatch
) -> None:
    settings = request.app.state.settings
    response.set_cookie(
        RECOVERY_CONTEXT_COOKIE,
        dispatch.context_token,
        max_age=600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path=RECOVERY_CONTEXT_PATH,
    )


def _clear_context_cookie(*, response: Response, request: Request) -> None:
    response.delete_cookie(
        RECOVERY_CONTEXT_COOKIE,
        path=RECOVERY_CONTEXT_PATH,
        secure=request.app.state.settings.cookie_secure,
        httponly=True,
        samesite="strict",
    )


def _request_origin_is_allowed(request: Request) -> bool:
    origin = request.headers.get("origin")
    if origin is None:
        referer = request.headers.get("referer")
        if referer is None:
            return False
        parsed = urlsplit(referer)
        origin = f"{parsed.scheme}://{parsed.netloc}"
    return origin in request.app.state.settings.cors_origins


def _context_invalid() -> JSONResponse:
    return _error(
        status_code=status.HTTP_409_CONFLICT,
        code="RECOVERY_CONTEXT_INVALID",
        message="恢复信息已失效，请重新开始。",
    )


def _csrf_error() -> JSONResponse:
    return _error(
        status_code=status.HTTP_403_FORBIDDEN,
        code="CSRF_ORIGIN_INVALID",
        message="请求来源无效。",
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
        "request_id": current_request_id(),
    }
    if retry_after is not None:
        error["retry_after"] = retry_after
    return JSONResponse(status_code=status_code, content={"error": error})
