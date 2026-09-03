"""HTTP-only admin probe; authorization truth remains in AdminService."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.admin.repository import SqlAlchemyAdminRepository
from app.admin.schemas import (
    AdminAuditPageResponse,
    AdminAuditQuery,
    AdminProbeResponse,
    CatalogDraftCreateCommand,
    CatalogDraftPatchCommand,
    CatalogDraftPreviewCommand,
    CatalogDraftPreviewResponse,
    CatalogDraftResponse,
    CatalogLifecycleCommand,
    CatalogPublicationResponse,
)
from app.admin.service import AdminAuditCursorInvalid, AdminPermissionDenied, AdminService, CatalogDraftConflict
from app.auth.api import AuthenticatedPrincipal
from app.auth.models import UserRole
from app.core.database import get_session
from fastapi import Request


router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def get_admin_service(request: Request, session: Session = Depends(get_session)) -> AdminService:
    """Bind the request transaction without allowing routes to touch ORM models."""

    return AdminService(
        repository=SqlAlchemyAdminRepository(session),
        commit=session.commit,
        rollback=session.rollback,
        cursor_secret=request.app.state.settings.secret_key.get_secret_value(),
    )


@router.get("/probe", response_model=AdminProbeResponse)
def probe(
    principal: AuthenticatedPrincipal,
    admin_service: AdminService = Depends(get_admin_service),
) -> AdminProbeResponse | JSONResponse:
    """Prove the endpoint is protected by session validation plus current DB RBAC."""

    try:
        admin_service.require_role(user_id=principal, required_role=UserRole.ADMIN)
    except AdminPermissionDenied:
        return _forbidden()
    return AdminProbeResponse()


@router.get("/audit", response_model=AdminAuditPageResponse)
def list_audit(
    principal: AuthenticatedPrincipal,
    query: AdminAuditQuery = Query(),
    admin_service: AdminService = Depends(get_admin_service),
) -> AdminAuditPageResponse | JSONResponse:
    """Read minimal audit evidence only after a fresh database role check."""

    try:
        admin_service.require_role(user_id=principal, required_role=UserRole.ADMIN)
        filters = query.model_dump()
        filters["actor_identifier"] = filters.pop("actor")
        return admin_service.list_audit_events(**filters)
    except AdminPermissionDenied:
        return _forbidden()
    except AdminAuditCursorInvalid as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid audit cursor") from error


@router.post("/catalog-drafts", response_model=CatalogDraftResponse, status_code=status.HTTP_201_CREATED)
def create_catalog_draft(
    command: CatalogDraftCreateCommand,
    principal: AuthenticatedPrincipal,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=16, max_length=160),
    admin_service: AdminService = Depends(get_admin_service),
) -> CatalogDraftResponse | JSONResponse:
    try:
        return admin_service.create_catalog_draft(actor_user_id=principal, command=command, command_key=idempotency_key)
    except AdminPermissionDenied:
        return _forbidden()
    except CatalogDraftConflict as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="catalog draft command conflict") from error


@router.post("/catalog-drafts/preview", response_model=CatalogDraftPreviewResponse)
def preview_catalog_draft(
    command: CatalogDraftPreviewCommand,
    principal: AuthenticatedPrincipal,
    admin_service: AdminService = Depends(get_admin_service),
) -> CatalogDraftPreviewResponse | JSONResponse:
    """Preview an allowlisted database-derived diff without mutating a draft."""

    try:
        return admin_service.preview_catalog_draft(actor_user_id=principal, command=command)
    except AdminPermissionDenied:
        return _forbidden()
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="catalog draft not found") from error
    except CatalogDraftConflict as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="catalog draft preview conflict") from error


@router.get("/catalog-drafts/{draft_id}", response_model=CatalogDraftResponse)
def read_catalog_draft(
    draft_id: uuid.UUID,
    principal: AuthenticatedPrincipal,
    admin_service: AdminService = Depends(get_admin_service),
) -> CatalogDraftResponse | JSONResponse:
    """Read the current safe draft projection after current database RBAC."""

    try:
        return admin_service.read_catalog_draft(actor_user_id=principal, draft_id=draft_id)
    except AdminPermissionDenied:
        return _forbidden()
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="catalog draft not found") from error


@router.patch("/catalog-drafts/{draft_id}", response_model=CatalogDraftResponse)
def patch_catalog_draft(
    draft_id: uuid.UUID,
    command: CatalogDraftPatchCommand,
    principal: AuthenticatedPrincipal,
    if_match: int = Header(alias="If-Match", ge=1),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=16, max_length=160),
    admin_service: AdminService = Depends(get_admin_service),
) -> CatalogDraftResponse | JSONResponse:
    try:
        return admin_service.patch_catalog_draft(
            actor_user_id=principal, draft_id=draft_id, expected_revision=if_match,
            command=command, command_key=idempotency_key,
        )
    except AdminPermissionDenied:
        return _forbidden()
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="catalog draft not found") from error
    except CatalogDraftConflict as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="catalog draft command conflict") from error


@router.post("/catalog-drafts/{draft_id}/review", response_model=CatalogPublicationResponse)
def review_catalog_draft(
    draft_id: uuid.UUID,
    command: CatalogLifecycleCommand,
    principal: AuthenticatedPrincipal,
    if_match: int = Header(alias="If-Match", ge=1),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=16, max_length=160),
    admin_service: AdminService = Depends(get_admin_service),
) -> CatalogPublicationResponse | JSONResponse:
    try:
        return admin_service.review_catalog_draft(actor_user_id=principal, draft_id=draft_id, expected_revision=if_match, command=command, command_key=idempotency_key)
    except AdminPermissionDenied:
        return _forbidden()
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="catalog draft not found") from error
    except CatalogDraftConflict as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="catalog lifecycle conflict") from error


@router.post("/catalog-drafts/{draft_id}/publish", response_model=CatalogPublicationResponse)
def publish_catalog_draft(
    draft_id: uuid.UUID,
    command: CatalogLifecycleCommand,
    principal: AuthenticatedPrincipal,
    if_match: int = Header(alias="If-Match", ge=1),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=16, max_length=160),
    admin_service: AdminService = Depends(get_admin_service),
) -> CatalogPublicationResponse | JSONResponse:
    try:
        return admin_service.publish_catalog_draft(actor_user_id=principal, draft_id=draft_id, expected_revision=if_match, command=command, command_key=idempotency_key)
    except AdminPermissionDenied:
        return _forbidden()
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="catalog draft not found") from error
    except CatalogDraftConflict as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="catalog lifecycle conflict") from error


@router.post("/catalog-publications/{publication_id}/disqualifications", response_model=CatalogPublicationResponse)
def disqualify_catalog_publication(
    publication_id: uuid.UUID,
    command: CatalogLifecycleCommand,
    principal: AuthenticatedPrincipal,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=16, max_length=160),
    admin_service: AdminService = Depends(get_admin_service),
) -> CatalogPublicationResponse | JSONResponse:
    try:
        return admin_service.disqualify_catalog_publication(actor_user_id=principal, publication_id=publication_id, command=command, command_key=idempotency_key)
    except AdminPermissionDenied:
        return _forbidden()
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="catalog publication not found") from error


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
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {"code": code, "message": message, "request_id": str(uuid.uuid4())}
        },
    )
