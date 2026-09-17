"""HTTP translation for authentication; business rules remain in services."""

from __future__ import annotations

from app.core.logging import current_request_id

import hashlib
import uuid
from urllib.parse import urlsplit
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, Security, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.repository import SqlAlchemyAuthRepository
from app.auth.schemas import (
    AccessTokenResponse,
    CodeDispatchAcceptedResponse,
    CurrentUserResponse,
    LoginRequest,
    RegisterRequest,
    VerificationCodeRequest,
    VerificationPendingResponse,
    VerificationSuccessResponse,
    SessionResponse,
)
from app.auth.security import InvalidAccessToken
from app.auth.service import (
    AuthenticatedUserUnavailable,
    AuthenticationService,
    InvalidCredentials,
    LoginRateLimited,
    InvalidVerificationCode,
    RegistrationDispatch,
    RegistrationService,
    ResendCooldown,
    VerificationAttemptsExceeded,
    VerificationCodeExpired,
    VerificationContextInvalid,
    CurrentSessionCannotBeRevoked,
    InvalidRefreshToken,
    RefreshTokenReplayed,
)
from app.core.database import get_session
from app.notifications.smtp import create_smtp_mail_provider


REGISTRATION_CONTEXT_COOKIE = "registration_context"
REFRESH_TOKEN_COOKIE = "refresh_token"
ACCESS_TOKEN_ISSUER = "food-agent-api"
ACCESS_TOKEN_AUDIENCE = "food-agent-h5"
REFRESH_COOKIE_MAX_AGE = 30 * 24 * 60 * 60
router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
users_router = APIRouter(prefix="/api/v1/users", tags=["users"])
bearer_scheme = HTTPBearer(auto_error=False)
_LOOPBACK_SOURCES = frozenset({"127.0.0.1", "::1", "localhost"})


def get_authentication_service(
    request: Request, session: Session = Depends(get_session)
) -> AuthenticationService:
    """Bind one request-scoped repository to login and identity policy."""

    settings = request.app.state.settings
    return AuthenticationService(
        repository=SqlAlchemyAuthRepository(session),
        secret_key=settings.secret_key.get_secret_value(),
        issuer=ACCESS_TOKEN_ISSUER,
        audience=ACCESS_TOKEN_AUDIENCE,
        commit=session.commit,
        rollback=session.rollback,
    )


def get_authenticated_principal(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    service: AuthenticationService = Depends(get_authentication_service),
) -> uuid.UUID:
    """Expose the authenticated user dependency once for every protected API module."""

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _principal_authentication_required()
    try:
        user_id, _session_id = service.authenticated_session(credentials.credentials)
    except (InvalidAccessToken, AuthenticatedUserUnavailable):
        raise _principal_authentication_required() from None
    return user_id


AuthenticatedPrincipal = Annotated[uuid.UUID, Depends(get_authenticated_principal)]


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
    "/register",
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


@router.get("/register/context", response_model=VerificationPendingResponse)
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


@router.post("/register/verify", response_model=VerificationSuccessResponse)
def verify_registration(
    payload: VerificationCodeRequest,
    response: Response,
    request: Request,
    registration_context: str | None = Cookie(default=None),
    service: RegistrationService = Depends(get_registration_service),
) -> VerificationSuccessResponse | JSONResponse:
    if not _request_origin_is_allowed(request):
        return _error(
            status_code=status.HTTP_403_FORBIDDEN,
            code="CSRF_ORIGIN_INVALID",
            message="请求来源无效。",
        )
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
    "/register/resend",
    response_model=CodeDispatchAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def resend_registration_code(
    response: Response,
    request: Request,
    registration_context: str | None = Cookie(default=None),
    service: RegistrationService = Depends(get_registration_service),
) -> CodeDispatchAcceptedResponse | JSONResponse:
    if not _request_origin_is_allowed(request):
        return _error(
            status_code=status.HTTP_403_FORBIDDEN,
            code="CSRF_ORIGIN_INVALID",
            message="请求来源无效。",
        )
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


@router.post("/login", response_model=AccessTokenResponse)
def login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    service: AuthenticationService = Depends(get_authentication_service),
) -> AccessTokenResponse | JSONResponse:
    try:
        source = _login_source(
            raw_source=request.client.host if request.client is not None else "unavailable",
            normalized_email=payload.email.strip().lower(),
            app_env=request.app.state.settings.app_env,
        )
        result = service.login(
            email=payload.email, password=payload.password, source=source
        )
    except LoginRateLimited as error:
        return _error(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="RATE_LIMITED",
            message="尝试次数过多，请稍后再试。",
            retry_after=error.retry_after,
        )
    except InvalidCredentials:
        return _error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTHENTICATION_FAILED",
            message="邮箱或密码不正确，或账号尚不可登录。",
        )
    _set_refresh_cookie(response=response, request=request, refresh_token=result.refresh_token)
    return AccessTokenResponse(
        access_token=result.access_token,
        token_type="bearer",
        expires_in=result.expires_in,
    )


def _login_source(*, raw_source: str, normalized_email: str, app_env: str) -> str:
    """Avoid one local browser's failed test accounts blocking every other account.

    Production and test keep the independent IP bucket that constrains password
    spraying. A Vite proxy makes every local browser request appear as loopback,
    so in local development only, scope that bucket to an opaque account digest.
    The service HMACs this value before persistence; neither raw email nor IP is
    stored in the login-attempt table.
    """

    source = raw_source.strip().lower() or "unavailable"
    if app_env == "local" and source in _LOOPBACK_SOURCES:
        email_digest = hashlib.sha256(normalized_email.encode("utf-8")).hexdigest()
        return f"local-loopback-principal:v1:{email_digest}"
    return source


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(
    response: Response,
    request: Request,
    refresh_token: str | None = Cookie(default=None, include_in_schema=False),
    service: AuthenticationService = Depends(get_authentication_service),
) -> AccessTokenResponse | JSONResponse:
    if not _request_origin_is_allowed(request):
        return _error(status_code=status.HTTP_403_FORBIDDEN, code="CSRF_ORIGIN_INVALID", message="请求来源无效。")
    if not refresh_token:
        return _refresh_invalid(response=response, request=request)
    try:
        result = service.refresh(refresh_token)
    except (InvalidRefreshToken, RefreshTokenReplayed):
        return _refresh_invalid(response=response, request=request)
    _set_refresh_cookie(response=response, request=request, refresh_token=result.refresh_token)
    return AccessTokenResponse(access_token=result.access_token, token_type="bearer", expires_in=result.expires_in)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def logout(
    response: Response,
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    service: AuthenticationService = Depends(get_authentication_service),
) -> Response | JSONResponse:
    if not _request_origin_is_allowed(request):
        return _error(status_code=status.HTTP_403_FORBIDDEN, code="CSRF_ORIGIN_INVALID", message="请求来源无效。")
    authenticated = _authenticated_session(credentials=credentials, service=service)
    if isinstance(authenticated, JSONResponse):
        return authenticated
    user_id, session_id = authenticated
    service.logout(user_id=user_id, session_id=session_id)
    _clear_refresh_cookie(response=response, request=request)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/sessions", response_model=list[SessionResponse])
def sessions(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    service: AuthenticationService = Depends(get_authentication_service),
) -> list[SessionResponse] | JSONResponse:
    authenticated = _authenticated_session(credentials=credentials, service=service)
    if isinstance(authenticated, JSONResponse):
        return authenticated
    user_id, session_id = authenticated
    return service.list_sessions(user_id=user_id, current_session_id=session_id)


@router.delete(
    "/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
def revoke_session(
    session_id: uuid.UUID,
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    service: AuthenticationService = Depends(get_authentication_service),
) -> Response | JSONResponse:
    if not _request_origin_is_allowed(request):
        return _error(status_code=status.HTTP_403_FORBIDDEN, code="CSRF_ORIGIN_INVALID", message="请求来源无效。")
    authenticated = _authenticated_session(credentials=credentials, service=service)
    if isinstance(authenticated, JSONResponse):
        return authenticated
    user_id, current_session_id = authenticated
    try:
        service.revoke_session(user_id=user_id, session_id=session_id, current_session_id=current_session_id)
    except CurrentSessionCannotBeRevoked:
        return _error(status_code=status.HTTP_409_CONFLICT, code="CURRENT_SESSION_REQUIRES_LOGOUT", message="当前会话请通过退出登录撤销。")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@users_router.get("/me", response_model=CurrentUserResponse)
def current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    service: AuthenticationService = Depends(get_authentication_service),
) -> CurrentUserResponse | JSONResponse:
    if credentials is None or credentials.scheme.lower() != "bearer":
        return _authentication_required()
    try:
        return service.current_user(credentials.credentials)
    except (InvalidAccessToken, AuthenticatedUserUnavailable):
        return _authentication_required()


def _authentication_required() -> JSONResponse:
    return _error(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code="AUTHENTICATION_REQUIRED",
        message="登录状态无效或已过期，请重新登录。",
    )


def _principal_authentication_required() -> HTTPException:
    """Dependency failures use FastAPI's standard bearer challenge, not a feature envelope."""

    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Bearer authentication is required.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _authenticated_session(
    *, credentials: HTTPAuthorizationCredentials | None, service: AuthenticationService
) -> tuple[uuid.UUID, uuid.UUID] | JSONResponse:
    if credentials is None or credentials.scheme.lower() != "bearer":
        return _authentication_required()
    try:
        return service.authenticated_session(credentials.credentials)
    except (InvalidAccessToken, AuthenticatedUserUnavailable):
        return _authentication_required()


def _request_origin_is_allowed(request: Request) -> bool:
    origin = request.headers.get("origin")
    if origin is None:
        referer = request.headers.get("referer")
        if referer is None:
            return False
        parsed = urlsplit(referer)
        origin = f"{parsed.scheme}://{parsed.netloc}"
    return origin in request.app.state.settings.cors_origins


def _set_refresh_cookie(*, response: Response, request: Request, refresh_token: str) -> None:
    response.set_cookie(
        REFRESH_TOKEN_COOKIE,
        refresh_token,
        max_age=REFRESH_COOKIE_MAX_AGE,
        httponly=True,
        secure=request.app.state.settings.cookie_secure,
        samesite="lax",
        path="/api/v1/auth",
    )


def _clear_refresh_cookie(*, response: Response, request: Request) -> None:
    response.delete_cookie(
        REFRESH_TOKEN_COOKIE,
        path="/api/v1/auth",
        secure=request.app.state.settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )


def _refresh_invalid(*, response: Response, request: Request) -> JSONResponse:
    error = _error(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code="REFRESH_TOKEN_INVALID",
        message="登录状态无效或已过期，请重新登录。",
    )
    _clear_refresh_cookie(response=error, request=request)
    return error


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
        "request_id": current_request_id(),
    }
    if retry_after is not None:
        error["retry_after"] = retry_after
    return JSONResponse(status_code=status_code, content={"error": error})
