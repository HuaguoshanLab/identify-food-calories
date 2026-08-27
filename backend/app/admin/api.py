"""HTTP-only admin probe; authorization truth remains in AdminService."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Security, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.admin.repository import SqlAlchemyAdminRepository
from app.admin.schemas import AdminProbeResponse
from app.admin.service import AdminPermissionDenied, AdminService
from app.auth.api import bearer_scheme, get_authentication_service
from app.auth.models import UserRole
from app.auth.security import InvalidAccessToken
from app.auth.service import AuthenticatedUserUnavailable, AuthenticationService
from app.core.database import get_session


router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def get_admin_service(session: Session = Depends(get_session)) -> AdminService:
    """Bind the request transaction without allowing routes to touch ORM models."""

    return AdminService(
        repository=SqlAlchemyAdminRepository(session),
        commit=session.commit,
        rollback=session.rollback,
    )


@router.get("/probe", response_model=AdminProbeResponse)
def probe(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    authentication_service: AuthenticationService = Depends(get_authentication_service),
    admin_service: AdminService = Depends(get_admin_service),
) -> AdminProbeResponse | JSONResponse:
    """Prove the endpoint is protected by session validation plus current DB RBAC."""

    if credentials is None or credentials.scheme.lower() != "bearer":
        return _authentication_required()
    try:
        user_id, _session_id = authentication_service.authenticated_session(
            credentials.credentials
        )
    except (InvalidAccessToken, AuthenticatedUserUnavailable):
        return _authentication_required()
    try:
        admin_service.require_role(user_id=user_id, required_role=UserRole.ADMIN)
    except AdminPermissionDenied:
        return _forbidden()
    return AdminProbeResponse()


def _authentication_required() -> JSONResponse:
    return _error(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code="AUTHENTICATION_REQUIRED",
        message="登录状态无效或已过期，请重新登录。",
    )


def _forbidden() -> JSONResponse:
    return _error(
        status_code=status.HTTP_403_FORBIDDEN,
        code="ADMIN_PERMISSION_REQUIRED",
        message="当前账号没有管理员权限。",
    )


def _error(*, status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message}})
