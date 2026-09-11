"""HTTP-only admin probe; authorization truth remains in AdminService."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from app.admin.repository import SqlAlchemyAdminRepository
from app.admin.catalog_csv import CatalogCsvInvalid
from app.admin.schemas import (
    AdminAuditPageResponse,
    AdminAuditQuery,
    AdminRunDetailResponse,
    AdminRunMetricsResponse,
    AdminRunPageResponse,
    AdminRunQuery,
    AdminProbeResponse,
    AdminRoleChangeCommand,
    AdminRoleChangeResponse,
    AdminRoleListResponse,
    AdminUserPageResponse,
    AdminUserQuery,
    CatalogDraftCreateCommand,
    CatalogDraftPatchCommand,
    CatalogDraftPreviewCommand,
    CatalogDraftPreviewResponse,
    CatalogDraftResponse,
    CatalogListQuery,
    CatalogListResponse,
    CatalogCsvInput,
    CatalogCsvPreview,
    CatalogCsvImportCommand,
    CatalogCsvImportResponse,
    CatalogLifecycleCommand,
    CatalogLifecyclePreviewResponse,
    CatalogPublicationResponse,
    CatalogEmbeddingRetryCommand,
    CatalogEmbeddingRetryResponse,
    CatalogEmbeddingStatusResponse,
    CatalogRelationEvidenceCommand,
    CatalogRelationEvidenceResponse,
    CatalogRelationEvidenceRevokeCommand,
    RuntimeConfigCommand,
    RuntimeConfigResponse,
    RecipeCandidateBulkCommand,
    RecipeCandidateCsvPreview,
    RecipeCandidateImportCommand,
    RecipeCandidateImportResponse,
    RecipeCandidateListQuery,
    RecipeCandidateListResponse,
)
from app.admin.service import (
    AdminAuditCursorInvalid,
    AdminPermissionDenied,
    AdminRoleChangeDenied,
    AdminRunCursorInvalid,
    AdminService,
    CatalogDraftConflict,
    CatalogEmbeddingRetryConflict,
    CatalogRelationEvidenceConflict,
    RecipeCandidateConflict,
    RuntimeConfigConflict,
)
from app.admin.recipe_csv import RecipeCandidateCsvInvalid
from app.auth.api import AuthenticatedPrincipal
from app.auth.models import UserRole
from app.core.database import get_session
from fastapi import Request


router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def get_admin_service(
    request: Request, session: Session = Depends(get_session)
) -> AdminService:
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


@router.get("/users", response_model=AdminUserPageResponse)
def list_users(principal: AuthenticatedPrincipal, query: AdminUserQuery = Query(), admin_service: AdminService = Depends(get_admin_service)) -> AdminUserPageResponse | JSONResponse:
    try:
        return admin_service.list_users(actor_user_id=principal, query=query)
    except AdminPermissionDenied:
        return _forbidden()


@router.get("/roles", response_model=AdminRoleListResponse)
def list_roles(principal: AuthenticatedPrincipal, admin_service: AdminService = Depends(get_admin_service)) -> AdminRoleListResponse | JSONResponse:
    try:
        return admin_service.list_roles(actor_user_id=principal)
    except AdminPermissionDenied:
        return _forbidden()


@router.patch("/users/{target_user_id}/role", response_model=AdminRoleChangeResponse)
def change_user_role(target_user_id: uuid.UUID, command: AdminRoleChangeCommand, principal: AuthenticatedPrincipal, idempotency_key: str = Header(alias="Idempotency-Key", min_length=16, max_length=160), admin_service: AdminService = Depends(get_admin_service)) -> AdminRoleChangeResponse | JSONResponse:
    try:
        return admin_service.change_user_role(actor_user_id=principal, target_user_id=target_user_id, after_role=UserRole(command.role), reason=command.reason, command_key=idempotency_key)
    except AdminPermissionDenied:
        return _forbidden()
    except KeyError as error:
        raise HTTPException(status_code=404, detail="user not found") from error
    except AdminRoleChangeDenied as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post(
    "/runtime-config",
    response_model=RuntimeConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
def configure_runtime(
    command: RuntimeConfigCommand,
    principal: AuthenticatedPrincipal,
    if_match: int = Header(alias="If-Match", ge=0),
    idempotency_key: str = Header(
        alias="Idempotency-Key", min_length=16, max_length=160
    ),
    admin_service: AdminService = Depends(get_admin_service),
) -> RuntimeConfigResponse | JSONResponse:
    """Create an immutable future-only policy version after fresh DB RBAC."""

    try:
        return admin_service.configure_runtime(
            actor_user_id=principal,
            command=command,
            command_key=idempotency_key,
            expected_version=if_match,
        )
    except AdminPermissionDenied:
        return _forbidden()
    except RuntimeConfigConflict as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="runtime config command conflict",
        ) from error


@router.get("/runtime-config", response_model=RuntimeConfigResponse)
def read_runtime_config(
    principal: AuthenticatedPrincipal,
    admin_service: AdminService = Depends(get_admin_service),
) -> RuntimeConfigResponse | JSONResponse:
    """Read the current non-secret policy after current database RBAC."""

    try:
        return admin_service.read_runtime_config(actor_user_id=principal)
    except AdminPermissionDenied:
        return _forbidden()
    except KeyError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="runtime config not found"
        ) from error


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
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid audit cursor",
        ) from error


@router.get("/runs/metrics", response_model=AdminRunMetricsResponse)
def run_metrics(
    principal: AuthenticatedPrincipal,
    query: AdminRunQuery = Query(),
    admin_service: AdminService = Depends(get_admin_service),
) -> AdminRunMetricsResponse | JSONResponse:
    """Use the same validated terminal filters as the runs keyset endpoint."""

    try:
        return admin_service.get_run_metrics(
            actor_user_id=principal, **query.model_dump(exclude={"limit", "cursor"})
        )
    except AdminPermissionDenied:
        return _forbidden()


@router.get("/runs", response_model=AdminRunPageResponse)
def list_runs(
    principal: AuthenticatedPrincipal,
    query: AdminRunQuery = Query(),
    admin_service: AdminService = Depends(get_admin_service),
) -> AdminRunPageResponse | JSONResponse:
    try:
        values = query.model_dump()
        return admin_service.list_agent_runs(actor_user_id=principal, **values)
    except AdminPermissionDenied:
        return _forbidden()
    except AdminRunCursorInvalid as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid run cursor",
        ) from error


@router.get("/runs/{run_id}", response_model=AdminRunDetailResponse)
def get_run(
    run_id: uuid.UUID,
    principal: AuthenticatedPrincipal,
    admin_service: AdminService = Depends(get_admin_service),
) -> AdminRunDetailResponse | JSONResponse:
    try:
        return admin_service.get_agent_run(actor_user_id=principal, run_id=run_id)
    except AdminPermissionDenied:
        return _forbidden()
    except KeyError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="agent run not found"
        ) from error


@router.get("/catalog-drafts", response_model=CatalogListResponse)
def list_catalog_drafts(
    principal: AuthenticatedPrincipal,
    query: CatalogListQuery = Query(),
    admin_service: AdminService = Depends(get_admin_service),
) -> CatalogListResponse | JSONResponse:
    try:
        return admin_service.list_catalog_drafts(actor_user_id=principal, query=query)
    except AdminPermissionDenied:
        return _forbidden()


@router.get("/recipe-candidates", response_model=RecipeCandidateListResponse)
def list_recipe_candidates(
    principal: AuthenticatedPrincipal,
    query: RecipeCandidateListQuery = Query(),
    admin_service: AdminService = Depends(get_admin_service),
) -> RecipeCandidateListResponse | JSONResponse:
    try:
        return admin_service.list_recipe_candidates(
            actor_user_id=principal, query=query
        )
    except AdminPermissionDenied:
        return _forbidden()


@router.get("/recipe-candidates/template")
def recipe_candidate_template(
    principal: AuthenticatedPrincipal,
    admin_service: AdminService = Depends(get_admin_service),
) -> Response:
    try:
        return Response(
            admin_service.recipe_candidate_csv_template(actor_user_id=principal),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="recipe-candidates-template.csv"',
                "Cache-Control": "no-store",
            },
        )
    except AdminPermissionDenied:
        return _forbidden()


@router.get("/recipe-candidates/export")
def export_recipe_candidates(
    principal: AuthenticatedPrincipal,
    query: RecipeCandidateListQuery = Query(),
    admin_service: AdminService = Depends(get_admin_service),
) -> Response:
    try:
        return Response(
            admin_service.export_recipe_candidate_csv(
                actor_user_id=principal, query=query
            ),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="recipe-candidates.csv"',
                "Cache-Control": "no-store",
            },
        )
    except AdminPermissionDenied:
        return _forbidden()
    except RecipeCandidateCsvInvalid as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post(
    "/recipe-candidates/import-preview", response_model=RecipeCandidateCsvPreview
)
def preview_recipe_candidates(
    command: CatalogCsvInput,
    principal: AuthenticatedPrincipal,
    admin_service: AdminService = Depends(get_admin_service),
) -> RecipeCandidateCsvPreview | JSONResponse:
    try:
        return admin_service.preview_recipe_candidate_csv(
            actor_user_id=principal, csv_text=command.csv_text
        )
    except AdminPermissionDenied:
        return _forbidden()
    except RecipeCandidateCsvInvalid as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post(
    "/recipe-candidates/import",
    response_model=RecipeCandidateImportResponse,
    status_code=201,
)
def import_recipe_candidates(
    command: RecipeCandidateImportCommand,
    principal: AuthenticatedPrincipal,
    idempotency_key: str = Header(
        alias="Idempotency-Key", min_length=16, max_length=160
    ),
    admin_service: AdminService = Depends(get_admin_service),
) -> RecipeCandidateImportResponse | JSONResponse:
    try:
        return admin_service.import_recipe_candidates(
            actor_user_id=principal, command=command, command_key=idempotency_key
        )
    except AdminPermissionDenied:
        return _forbidden()
    except RecipeCandidateCsvInvalid as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except RecipeCandidateConflict as error:
        raise HTTPException(
            status_code=409, detail="recipe candidate import conflict"
        ) from error


@router.post("/recipe-candidates/{operation}")
def change_recipe_candidate_status(
    operation: Literal["enable", "disable", "delete"],
    command: RecipeCandidateBulkCommand,
    principal: AuthenticatedPrincipal,
    idempotency_key: str = Header(
        alias="Idempotency-Key", min_length=16, max_length=160
    ),
    admin_service: AdminService = Depends(get_admin_service),
):
    try:
        return admin_service.change_recipe_candidate_status(
            actor_user_id=principal,
            command=command,
            status={"enable": "enabled", "disable": "disabled", "delete": "deleted"}[
                operation
            ],
            command_key=idempotency_key,
        )
    except AdminPermissionDenied:
        return _forbidden()
    except KeyError as error:
        raise HTTPException(
            status_code=404, detail="recipe candidate not found"
        ) from error
    except RecipeCandidateConflict as error:
        raise HTTPException(
            status_code=409, detail="recipe candidate command conflict"
        ) from error


@router.get("/catalog-drafts/export")
def export_catalog_csv(
    principal: AuthenticatedPrincipal,
    query: CatalogListQuery = Query(),
    admin_service: AdminService = Depends(get_admin_service),
) -> Response:
    try:
        content = admin_service.export_catalog_csv(actor_user_id=principal, query=query)
        return Response(
            content,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="nutrition-catalog.csv"',
                "Cache-Control": "no-store",
            },
        )
    except AdminPermissionDenied:
        return _forbidden()
    except CatalogCsvInvalid as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/catalog-drafts/template")
def catalog_csv_template(
    principal: AuthenticatedPrincipal,
    admin_service: AdminService = Depends(get_admin_service),
) -> Response:
    try:
        return Response(
            admin_service.catalog_csv_template(actor_user_id=principal),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="nutrition-catalog-template.csv"',
                "Cache-Control": "no-store",
            },
        )
    except AdminPermissionDenied:
        return _forbidden()


@router.post("/catalog-drafts/import-preview", response_model=CatalogCsvPreview)
def preview_catalog_csv(
    command: CatalogCsvInput,
    principal: AuthenticatedPrincipal,
    admin_service: AdminService = Depends(get_admin_service),
) -> CatalogCsvPreview | JSONResponse:
    try:
        return admin_service.preview_catalog_csv(
            actor_user_id=principal, csv_text=command.csv_text
        )
    except AdminPermissionDenied:
        return _forbidden()
    except CatalogCsvInvalid as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post(
    "/catalog-drafts/import", response_model=CatalogCsvImportResponse, status_code=201
)
def import_catalog_csv(
    command: CatalogCsvImportCommand,
    principal: AuthenticatedPrincipal,
    idempotency_key: str = Header(
        alias="Idempotency-Key", min_length=16, max_length=160
    ),
    admin_service: AdminService = Depends(get_admin_service),
) -> CatalogCsvImportResponse | JSONResponse:
    try:
        return admin_service.import_catalog_csv(
            actor_user_id=principal, command=command, command_key=idempotency_key
        )
    except AdminPermissionDenied:
        return _forbidden()
    except CatalogCsvInvalid as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except CatalogDraftConflict as error:
        raise HTTPException(
            status_code=409, detail="catalog import conflict"
        ) from error


@router.post(
    "/catalog-drafts",
    response_model=CatalogDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_catalog_draft(
    command: CatalogDraftCreateCommand,
    principal: AuthenticatedPrincipal,
    idempotency_key: str = Header(
        alias="Idempotency-Key", min_length=16, max_length=160
    ),
    admin_service: AdminService = Depends(get_admin_service),
) -> CatalogDraftResponse | JSONResponse:
    try:
        return admin_service.create_catalog_draft(
            actor_user_id=principal, command=command, command_key=idempotency_key
        )
    except AdminPermissionDenied:
        return _forbidden()
    except CatalogDraftConflict as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="catalog draft command conflict",
        ) from error


@router.post("/catalog-drafts/preview", response_model=CatalogDraftPreviewResponse)
def preview_catalog_draft(
    command: CatalogDraftPreviewCommand,
    principal: AuthenticatedPrincipal,
    admin_service: AdminService = Depends(get_admin_service),
) -> CatalogDraftPreviewResponse | JSONResponse:
    """Preview an allowlisted database-derived diff without mutating a draft."""

    try:
        return admin_service.preview_catalog_draft(
            actor_user_id=principal, command=command
        )
    except AdminPermissionDenied:
        return _forbidden()
    except KeyError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="catalog draft not found"
        ) from error
    except CatalogDraftConflict as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="catalog draft preview conflict",
        ) from error


@router.get("/catalog-drafts/{draft_id}", response_model=CatalogDraftResponse)
def read_catalog_draft(
    draft_id: uuid.UUID,
    principal: AuthenticatedPrincipal,
    admin_service: AdminService = Depends(get_admin_service),
) -> CatalogDraftResponse | JSONResponse:
    """Read the current safe draft projection after current database RBAC."""

    try:
        return admin_service.read_catalog_draft(
            actor_user_id=principal, draft_id=draft_id
        )
    except AdminPermissionDenied:
        return _forbidden()
    except KeyError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="catalog draft not found"
        ) from error


@router.get(
    "/catalog-drafts/{draft_id}/lifecycle-preview",
    response_model=CatalogLifecyclePreviewResponse,
)
def preview_catalog_lifecycle(
    draft_id: uuid.UUID,
    principal: AuthenticatedPrincipal,
    admin_service: AdminService = Depends(get_admin_service),
) -> CatalogLifecyclePreviewResponse | JSONResponse:
    """Return server-derived confirmation evidence without changing lifecycle state."""

    try:
        return admin_service.preview_catalog_lifecycle(
            actor_user_id=principal, draft_id=draft_id
        )
    except AdminPermissionDenied:
        return _forbidden()
    except KeyError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="catalog draft not found"
        ) from error
    except CatalogDraftConflict as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="catalog lifecycle preview conflict",
        ) from error


@router.patch("/catalog-drafts/{draft_id}", response_model=CatalogDraftResponse)
def patch_catalog_draft(
    draft_id: uuid.UUID,
    command: CatalogDraftPatchCommand,
    principal: AuthenticatedPrincipal,
    if_match: int = Header(alias="If-Match", ge=1),
    idempotency_key: str = Header(
        alias="Idempotency-Key", min_length=16, max_length=160
    ),
    admin_service: AdminService = Depends(get_admin_service),
) -> CatalogDraftResponse | JSONResponse:
    try:
        return admin_service.patch_catalog_draft(
            actor_user_id=principal,
            draft_id=draft_id,
            expected_revision=if_match,
            command=command,
            command_key=idempotency_key,
        )
    except AdminPermissionDenied:
        return _forbidden()
    except KeyError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="catalog draft not found"
        ) from error
    except CatalogDraftConflict as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="catalog draft command conflict",
        ) from error


@router.post(
    "/catalog-drafts/{draft_id}/review", response_model=CatalogPublicationResponse
)
def review_catalog_draft(
    draft_id: uuid.UUID,
    command: CatalogLifecycleCommand,
    principal: AuthenticatedPrincipal,
    if_match: int = Header(alias="If-Match", ge=1),
    idempotency_key: str = Header(
        alias="Idempotency-Key", min_length=16, max_length=160
    ),
    admin_service: AdminService = Depends(get_admin_service),
) -> CatalogPublicationResponse | JSONResponse:
    try:
        return admin_service.review_catalog_draft(
            actor_user_id=principal,
            draft_id=draft_id,
            expected_revision=if_match,
            command=command,
            command_key=idempotency_key,
        )
    except AdminPermissionDenied:
        return _forbidden()
    except KeyError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="catalog draft not found"
        ) from error
    except CatalogDraftConflict as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="catalog lifecycle conflict"
        ) from error


@router.post(
    "/catalog-drafts/{draft_id}/publish", response_model=CatalogPublicationResponse
)
def publish_catalog_draft(
    draft_id: uuid.UUID,
    command: CatalogLifecycleCommand,
    principal: AuthenticatedPrincipal,
    if_match: int = Header(alias="If-Match", ge=1),
    idempotency_key: str = Header(
        alias="Idempotency-Key", min_length=16, max_length=160
    ),
    admin_service: AdminService = Depends(get_admin_service),
) -> CatalogPublicationResponse | JSONResponse:
    try:
        return admin_service.publish_catalog_draft(
            actor_user_id=principal,
            draft_id=draft_id,
            expected_revision=if_match,
            command=command,
            command_key=idempotency_key,
        )
    except AdminPermissionDenied:
        return _forbidden()
    except KeyError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="catalog draft not found"
        ) from error
    except CatalogDraftConflict as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="catalog lifecycle conflict"
        ) from error


@router.post(
    "/catalog-publications/{publication_id}/disqualifications",
    response_model=CatalogPublicationResponse,
)
def disqualify_catalog_publication(
    publication_id: uuid.UUID,
    command: CatalogLifecycleCommand,
    principal: AuthenticatedPrincipal,
    idempotency_key: str = Header(
        alias="Idempotency-Key", min_length=16, max_length=160
    ),
    admin_service: AdminService = Depends(get_admin_service),
) -> CatalogPublicationResponse | JSONResponse:
    try:
        return admin_service.disqualify_catalog_publication(
            actor_user_id=principal,
            publication_id=publication_id,
            command=command,
            command_key=idempotency_key,
        )
    except AdminPermissionDenied:
        return _forbidden()
    except KeyError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="catalog publication not found",
        ) from error


@router.get(
    "/catalog-publications/{publication_id}/embedding-status",
    response_model=CatalogEmbeddingStatusResponse,
)
def catalog_embedding_status(
    publication_id: uuid.UUID,
    principal: AuthenticatedPrincipal,
    admin_service: AdminService = Depends(get_admin_service),
) -> CatalogEmbeddingStatusResponse | JSONResponse:
    try:
        return admin_service.get_catalog_embedding_status(
            actor_user_id=principal, publication_id=publication_id
        )
    except AdminPermissionDenied:
        return _forbidden()
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="catalog publication not found") from error


@router.post(
    "/catalog-publications/{publication_id}/embedding-retries",
    response_model=CatalogEmbeddingRetryResponse,
)
def retry_catalog_embedding_jobs(
    publication_id: uuid.UUID,
    command: CatalogEmbeddingRetryCommand,
    principal: AuthenticatedPrincipal,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=16, max_length=160),
    admin_service: AdminService = Depends(get_admin_service),
) -> CatalogEmbeddingRetryResponse | JSONResponse:
    try:
        return admin_service.retry_catalog_embedding_jobs(
            actor_user_id=principal,
            publication_id=publication_id,
            command=command.model_copy(update={"idempotency_key": idempotency_key}),
        )
    except AdminPermissionDenied:
        return _forbidden()
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="catalog publication not found") from error
    except CatalogEmbeddingRetryConflict as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="embedding retry conflict") from error


@router.post(
    "/catalog-relation-evidence",
    response_model=CatalogRelationEvidenceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_catalog_relation_evidence(
    command: CatalogRelationEvidenceCommand,
    principal: AuthenticatedPrincipal,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=16, max_length=160),
    admin_service: AdminService = Depends(get_admin_service),
) -> CatalogRelationEvidenceResponse | JSONResponse:
    try:
        return admin_service.create_catalog_relation_evidence(
            actor_user_id=principal, command=command, command_key=idempotency_key
        )
    except AdminPermissionDenied:
        return _forbidden()
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="relation publication version not found") from error
    except CatalogRelationEvidenceConflict as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="relation evidence conflict") from error


@router.post(
    "/catalog-relation-evidence/{evidence_id}/revocations",
    response_model=CatalogRelationEvidenceResponse,
)
def revoke_catalog_relation_evidence(
    evidence_id: uuid.UUID,
    command: CatalogRelationEvidenceRevokeCommand,
    principal: AuthenticatedPrincipal,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=16, max_length=160),
    admin_service: AdminService = Depends(get_admin_service),
) -> CatalogRelationEvidenceResponse | JSONResponse:
    try:
        return admin_service.revoke_catalog_relation_evidence(
            actor_user_id=principal,
            evidence_id=evidence_id,
            command=command,
            command_key=idempotency_key,
        )
    except AdminPermissionDenied:
        return _forbidden()
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="catalog relation evidence not found") from error
    except CatalogRelationEvidenceConflict as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="relation evidence conflict") from error


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
