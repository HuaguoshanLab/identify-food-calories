"""HTTP contracts for strict catalog draft commands."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.admin.api import get_admin_service
from app.admin.schemas import CatalogDraftPreviewResponse, CatalogDraftResponse, CatalogLifecyclePreviewResponse
from app.admin.service import AdminPermissionDenied
from app.agent.graph import NoopAgentRuntimeFactory
from app.auth.api import get_authenticated_principal
from app.main import create_app


class StubCatalogService:
    def require_role(self, **_kwargs: object) -> None:
        return None

    def create_catalog_draft(self, **_kwargs: object) -> CatalogDraftResponse:
        return CatalogDraftResponse(
            id=uuid.uuid4(), canonical_name="Oats", aliases=["rolled oats"], energy_kcal_per_100g="389",
            protein_g_per_100g="16.9", fat_g_per_100g="6.9", carbohydrate_g_per_100g="66.3",
            source_name="USDA", source_url="https://fdc.nal.usda.gov/", authorization_status="authorized", revision=1,
        )

    def read_catalog_draft(self, **_kwargs: object) -> CatalogDraftResponse:
        return self.create_catalog_draft()

    def preview_catalog_draft(self, **_kwargs: object) -> CatalogDraftPreviewResponse:
        return CatalogDraftPreviewResponse(
            draft_id=None,
            base_revision=0,
            field_diffs=[{"field": "canonical_name", "before": None, "after": "Oats"}],
            impact_categories=["catalog_identity"],
        )

    def preview_catalog_lifecycle(self, **_kwargs: object) -> CatalogLifecyclePreviewResponse:
        return CatalogLifecyclePreviewResponse(
            draft=self.read_catalog_draft(),
            publication=None,
            field_diffs=[{
                "field": "canonical_name", "before": None, "after": "Oats", "change": "added",
            }],
            impact={"affected_catalog_items": 1, "description": "首次发布后，新分析将使用不可变版本。"},
        )


def _payload() -> dict[str, object]:
    return {
        "canonical_name": "Oats", "aliases": ["rolled oats"], "energy_kcal_per_100g": "389",
        "protein_g_per_100g": "16.9", "fat_g_per_100g": "6.9", "carbohydrate_g_per_100g": "66.3",
        "source_name": "USDA", "source_url": "https://fdc.nal.usda.gov/", "authorization_status": "authorized",
        "reason": "verified source import",
    }


def test_catalog_create_requires_admin_headers_and_returns_safe_projection() -> None:
    app = create_app(runtime_factory=NoopAgentRuntimeFactory())
    app.dependency_overrides[get_authenticated_principal] = lambda: uuid.uuid4()
    app.dependency_overrides[get_admin_service] = StubCatalogService
    with TestClient(app) as client:
        missing_key = client.post("/api/v1/admin/catalog-drafts", json=_payload())
        response = client.post("/api/v1/admin/catalog-drafts", json=_payload(), headers={"Idempotency-Key": "catalog-create-00000001"})
    assert missing_key.status_code == 422
    assert response.status_code == 201
    assert "before_diff" not in response.json()
    assert "after_diff" not in response.json()


def test_catalog_patch_requires_if_match() -> None:
    app = create_app(runtime_factory=NoopAgentRuntimeFactory())
    app.dependency_overrides[get_authenticated_principal] = lambda: uuid.uuid4()
    app.dependency_overrides[get_admin_service] = StubCatalogService
    with TestClient(app) as client:
        response = client.patch(
            f"/api/v1/admin/catalog-drafts/{uuid.uuid4()}", json={"canonical_name": "Oats", "reason": "label correction"},
            headers={"Idempotency-Key": "catalog-patch-00000001"},
        )
    assert response.status_code == 422


def test_catalog_preview_and_read_are_rbac_protected_safe_projections() -> None:
    app = create_app(runtime_factory=NoopAgentRuntimeFactory())
    app.dependency_overrides[get_authenticated_principal] = lambda: uuid.uuid4()
    app.dependency_overrides[get_admin_service] = StubCatalogService
    preview_payload = {key: value for key, value in _payload().items() if key != "reason"}
    with TestClient(app) as client:
        preview = client.post("/api/v1/admin/catalog-drafts/preview", json=preview_payload | {"draft_id": None})
        read = client.get(f"/api/v1/admin/catalog-drafts/{uuid.uuid4()}")
        lifecycle = client.get(f"/api/v1/admin/catalog-drafts/{uuid.uuid4()}/lifecycle-preview")
    assert preview.status_code == 200
    assert preview.json() == {
        "draft_id": None,
        "base_revision": 0,
        "field_diffs": [{"field": "canonical_name", "before": None, "after": "Oats"}],
        "impact_categories": ["catalog_identity"],
    }
    assert "reason" not in read.json()
    assert "before_diff" not in read.json()
    assert read.status_code == 200
    assert lifecycle.status_code == 200
    assert lifecycle.json()["field_diffs"] == [{"field": "canonical_name", "before": None, "after": "Oats", "change": "added"}]
    assert "snapshot" not in lifecycle.json()
    assert "command_key" not in lifecycle.json()


def test_all_catalog_commands_map_database_rbac_denial_to_forbidden() -> None:
    class DeniedCatalogService(StubCatalogService):
        def create_catalog_draft(self, **_kwargs: object) -> CatalogDraftResponse:
            raise AdminPermissionDenied("database role does not permit this operation")

        def patch_catalog_draft(self, **_kwargs: object) -> CatalogDraftResponse:
            raise AdminPermissionDenied("database role does not permit this operation")

        def publish_catalog_draft(self, **_kwargs: object) -> object:
            raise AdminPermissionDenied("database role does not permit this operation")

        def disqualify_catalog_publication(self, **_kwargs: object) -> object:
            raise AdminPermissionDenied("database role does not permit this operation")

    app = create_app(runtime_factory=NoopAgentRuntimeFactory())
    app.dependency_overrides[get_authenticated_principal] = lambda: uuid.uuid4()
    app.dependency_overrides[get_admin_service] = DeniedCatalogService
    draft_id = uuid.uuid4()
    publication_id = uuid.uuid4()
    with TestClient(app) as client:
        responses = [client.post(
            "/api/v1/admin/catalog-drafts", json=_payload(),
            headers={"Idempotency-Key": "catalog-create-00000002"},
        ), client.patch(
            f"/api/v1/admin/catalog-drafts/{draft_id}", json={"canonical_name": "Oats", "reason": "label correction"},
            headers={"If-Match": "1", "Idempotency-Key": "catalog-patch-00000002"},
        ), client.post(
            f"/api/v1/admin/catalog-drafts/{draft_id}/publish", json={"reason": "approved publication", "confirm": True},
            headers={"If-Match": "1", "Idempotency-Key": "catalog-publish-00000002"},
        ), client.post(
            f"/api/v1/admin/catalog-publications/{publication_id}/disqualifications", json={"reason": "authorization revoked", "confirm": True},
            headers={"Idempotency-Key": "catalog-disqualify-00000002"},
        )]
    assert [response.status_code for response in responses] == [403, 403, 403, 403]
    assert [response.json()["error"]["code"] for response in responses] == ["ADMIN_PERMISSION_REQUIRED"] * 4


def test_catalog_read_and_preview_map_database_rbac_denial_to_forbidden() -> None:
    class DeniedCatalogService(StubCatalogService):
        def read_catalog_draft(self, **_kwargs: object) -> CatalogDraftResponse:
            raise AdminPermissionDenied("database role does not permit this operation")

        def preview_catalog_draft(self, **_kwargs: object) -> CatalogDraftPreviewResponse:
            raise AdminPermissionDenied("database role does not permit this operation")

        def preview_catalog_lifecycle(self, **_kwargs: object) -> CatalogLifecyclePreviewResponse:
            raise AdminPermissionDenied("database role does not permit this operation")

    app = create_app(runtime_factory=NoopAgentRuntimeFactory())
    app.dependency_overrides[get_authenticated_principal] = lambda: uuid.uuid4()
    app.dependency_overrides[get_admin_service] = DeniedCatalogService
    preview_payload = {key: value for key, value in _payload().items() if key != "reason"}
    with TestClient(app) as client:
        preview = client.post("/api/v1/admin/catalog-drafts/preview", json=preview_payload | {"draft_id": None})
        read = client.get(f"/api/v1/admin/catalog-drafts/{uuid.uuid4()}")
        lifecycle = client.get(f"/api/v1/admin/catalog-drafts/{uuid.uuid4()}/lifecycle-preview")
    assert preview.status_code == 403
    assert read.status_code == 403
    assert preview.json()["error"]["code"] == "ADMIN_PERMISSION_REQUIRED"
    assert read.json()["error"]["code"] == "ADMIN_PERMISSION_REQUIRED"
    assert lifecycle.status_code == 403
    assert lifecycle.json()["error"]["code"] == "ADMIN_PERMISSION_REQUIRED"
