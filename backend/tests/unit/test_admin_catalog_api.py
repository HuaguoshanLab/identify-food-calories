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

    def get_catalog_embedding_status(self, *, publication_id: uuid.UUID, **_kwargs: object):
        from app.admin.schemas import CatalogEmbeddingStatusResponse

        return CatalogEmbeddingStatusResponse(
            publication_id=publication_id,
            status="pending",
            pending_count=1,
            processing_count=0,
            failed_count=0,
            completed_count=0,
            jobs=[],
        )

    def retry_catalog_embedding_jobs(self, *, publication_id: uuid.UUID, **_kwargs: object):
        from app.admin.schemas import CatalogEmbeddingRetryResponse

        return CatalogEmbeddingRetryResponse(
            **self.get_catalog_embedding_status(publication_id=publication_id).model_dump(),
            reset_count=1,
        )

    def create_catalog_vector_space_build(self, **_kwargs: object):
        from app.admin.schemas import CatalogVectorSpaceBuildResponse

        return CatalogVectorSpaceBuildResponse(
            id=uuid.uuid4(), vector_space_id=uuid.uuid4(), embedding_model="text-embedding-v4",
            embedding_dimension=1024, adapter_version="v1", retrieval_version="hybrid-v1",
            snapshot_hash="a" * 64, expected_name_count=2, pending_count=2,
            failed_count=0, completed_count=0, status="pending",
        )

    def backfill_catalog_search_index(self, **_kwargs: object):
        from app.admin.schemas import CatalogSearchIndexBackfillResponse
        return CatalogSearchIndexBackfillResponse(
            audit_id=uuid.uuid4(), publication_count=1, name_count=2, embedding_job_count=0,
        )

    def create_catalog_relation_evidence(self, *, command, **_kwargs: object):
        source_publication_id = command.source_publication_id
        target_publication_id = command.target_publication_id
        from app.admin.schemas import CatalogRelationEvidenceResponse

        return CatalogRelationEvidenceResponse(
            id=uuid.uuid4(),
            source_publication_id=source_publication_id,
            target_publication_id=target_publication_id,
            relation="name_variant",
            status="active",
        )

    def revoke_catalog_relation_evidence(self, *, evidence_id: uuid.UUID, **_kwargs: object):
        from app.admin.schemas import CatalogRelationEvidenceResponse

        return CatalogRelationEvidenceResponse(
            id=evidence_id,
            source_publication_id=uuid.uuid4(),
            target_publication_id=uuid.uuid4(),
            relation="name_variant",
            status="revoked",
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


def test_catalog_list_csv_http_routes_and_validation() -> None:
    from app.admin.catalog_csv import CatalogCsvInvalid, write_catalog_csv
    from app.admin.schemas import CatalogCsvImportResponse, CatalogCsvPreview, CatalogListResponse

    class ExchangeService(StubCatalogService):
        def list_catalog_drafts(self, *, query, **_kwargs):
            assert query.search == '燕麦' and query.page == 2
            return CatalogListResponse(items=[], total=0, page=query.page, page_size=query.page_size)

        def catalog_csv_template(self, **_kwargs):
            return write_catalog_csv([])

        def export_catalog_csv(self, **_kwargs):
            return write_catalog_csv([self.create_catalog_draft()])

        def preview_catalog_csv(self, *, csv_text, **_kwargs):
            if csv_text == 'invalid':
                raise CatalogCsvInvalid('表头不匹配。')
            return CatalogCsvPreview(total_rows=1, valid_rows=0, rows=[], errors=[{'row': 2, 'field': '来源链接', 'message': '请核对来源。'}])

        def import_catalog_csv(self, **_kwargs):
            return CatalogCsvImportResponse(imported_count=1, draft_ids=[uuid.uuid4()])

    app = create_app(runtime_factory=NoopAgentRuntimeFactory())
    app.dependency_overrides[get_authenticated_principal] = lambda: uuid.uuid4()
    app.dependency_overrides[get_admin_service] = ExchangeService
    with TestClient(app) as client:
        assert client.get('/api/v1/admin/catalog-drafts', params={'search': '燕麦', 'page': 2}).json()['page'] == 2
        assert client.get('/api/v1/admin/catalog-drafts?page_size=101').status_code == 422
        assert client.get('/api/v1/admin/catalog-drafts?authorization_status=unknown').status_code == 422
        for endpoint in ['template', 'export']:
            response = client.get(f'/api/v1/admin/catalog-drafts/{endpoint}')
            assert response.status_code == 200
            assert response.headers['content-type'].startswith('text/csv')
            assert response.headers['cache-control'] == 'no-store'
            assert response.content.startswith(b'\xef\xbb\xbf')
        assert client.post('/api/v1/admin/catalog-drafts/import-preview', json={'csv_text': 'invalid'}).status_code == 422
        preview = client.post('/api/v1/admin/catalog-drafts/import-preview', json={'csv_text': 'example'})
        assert preview.json()['errors'][0]['row'] == 2
        command = {'csv_text': 'example', 'reason': 'test', 'confirm': True}
        assert client.post('/api/v1/admin/catalog-drafts/import', json=command).status_code == 422
        response = client.post('/api/v1/admin/catalog-drafts/import', json=command, headers={'Idempotency-Key': 'csv-import-00000001'})
        assert response.status_code == 201 and response.json()['imported_count'] == 1


def test_csv_list_export_preview_import_deny_non_admin_over_http():
    class DeniedService(StubCatalogService):
        def list_catalog_drafts(self, **_kwargs):
            raise AdminPermissionDenied()
        export_catalog_csv = list_catalog_drafts
        catalog_csv_template = list_catalog_drafts
        preview_catalog_csv = list_catalog_drafts
        import_catalog_csv = list_catalog_drafts

    app = create_app(runtime_factory=NoopAgentRuntimeFactory())
    app.dependency_overrides[get_authenticated_principal] = lambda: uuid.uuid4()
    app.dependency_overrides[get_admin_service] = DeniedService
    with TestClient(app) as client:
        for path in ['', '/export', '/template']:
            assert client.get('/api/v1/admin/catalog-drafts' + path).status_code == 403
        assert client.post('/api/v1/admin/catalog-drafts/import-preview', json={'csv_text': 'test'}).status_code == 403
        assert client.post('/api/v1/admin/catalog-drafts/import', json={'csv_text': 'test', 'reason': 'test', 'confirm': True}, headers={'Idempotency-Key': 'csv-import-00000001'}).status_code == 403


def test_catalog_embedding_control_plane_is_publication_scoped_and_safe() -> None:
    app = create_app(runtime_factory=NoopAgentRuntimeFactory())
    app.dependency_overrides[get_authenticated_principal] = lambda: uuid.uuid4()
    app.dependency_overrides[get_admin_service] = StubCatalogService
    publication_id = uuid.uuid4()
    with TestClient(app) as client:
        status = client.get(f"/api/v1/admin/catalog-publications/{publication_id}/embedding-status")
        missing_key = client.post(
            f"/api/v1/admin/catalog-publications/{publication_id}/embedding-retries",
            json={"reason": "provider recovered"},
        )
        retry = client.post(
            f"/api/v1/admin/catalog-publications/{publication_id}/embedding-retries",
            json={"reason": "provider recovered"},
            headers={"Idempotency-Key": "embedding-retry-00000001"},
        )
    assert status.status_code == 200
    assert status.json()["publication_id"] == str(publication_id)
    assert {"pending_count", "processing_count", "failed_count", "completed_count", "jobs"} <= status.json().keys()
    assert "display_name" not in status.json()
    assert missing_key.status_code == 422
    assert retry.status_code == 200
    assert retry.json()["reset_count"] == 1


def test_vector_space_build_requires_admin_idempotency_and_pinned_identity() -> None:
    app = create_app(runtime_factory=NoopAgentRuntimeFactory())
    app.dependency_overrides[get_authenticated_principal] = lambda: uuid.uuid4()
    app.dependency_overrides[get_admin_service] = StubCatalogService
    payload = {
        "embedding_model": "text-embedding-v4", "embedding_dimension": 1024,
        "adapter_version": "v1", "retrieval_version": "hybrid-v1",
        "reason": "backfill current qualified names", "confirm": True,
    }
    with TestClient(app) as client:
        assert client.post("/api/v1/admin/vector-space-builds", json=payload).status_code == 422
        response = client.post(
            "/api/v1/admin/vector-space-builds", json=payload,
            headers={"Idempotency-Key": "vector-space-build-000001"},
        )
        assert client.post(
            "/api/v1/admin/vector-space-builds", json=payload | {"embedding_dimension": 9},
            headers={"Idempotency-Key": "vector-space-build-000002"},
        ).status_code == 422
    assert response.status_code == 201
    assert response.json()["status"] == "pending"


def test_catalog_search_index_backfill_requires_explicit_admin_command() -> None:
    app = create_app(runtime_factory=NoopAgentRuntimeFactory())
    app.dependency_overrides[get_authenticated_principal] = lambda: uuid.uuid4()
    app.dependency_overrides[get_admin_service] = StubCatalogService
    payload = {"reason": "repair legacy derived search names", "confirm": True}
    with TestClient(app) as client:
        assert client.post("/api/v1/admin/catalog-search-index-backfills", json=payload).status_code == 422
        assert client.post("/api/v1/admin/catalog-search-index-backfills", json={"reason": " ", "confirm": True}, headers={"Idempotency-Key": "index-backfill-0001"}).status_code == 422
        response = client.post("/api/v1/admin/catalog-search-index-backfills", json=payload, headers={"Idempotency-Key": "index-backfill-0001"})
    assert response.status_code == 201
    assert response.json()["name_count"] == 2
    assert "display_name" not in response.json()


def test_catalog_relation_evidence_requires_bounded_idempotent_admin_command() -> None:
    app = create_app(runtime_factory=NoopAgentRuntimeFactory())
    app.dependency_overrides[get_authenticated_principal] = lambda: uuid.uuid4()
    app.dependency_overrides[get_admin_service] = StubCatalogService
    source_publication_id, target_publication_id = uuid.uuid4(), uuid.uuid4()
    command = {
        "source_publication_id": str(source_publication_id),
        "source_name_id": str(uuid.uuid4()),
        "target_publication_id": str(target_publication_id),
        "target_name_id": str(uuid.uuid4()),
        "relation": "name_variant",
        "reason": "controlled synonym evidence",
    }
    with TestClient(app) as client:
        missing_key = client.post("/api/v1/admin/catalog-relation-evidence", json=command)
        created = client.post(
            "/api/v1/admin/catalog-relation-evidence",
            json=command,
            headers={"Idempotency-Key": "relation-create-00000001"},
        )
        invalid = client.post(
            "/api/v1/admin/catalog-relation-evidence",
            json=command | {"relation": "made_up_relation"},
            headers={"Idempotency-Key": "relation-create-00000002"},
        )
        revoked = client.post(
            f"/api/v1/admin/catalog-relation-evidence/{uuid.uuid4()}/revocations",
            json={"reason": "evidence superseded"},
            headers={"Idempotency-Key": "relation-revoke-00000001"},
        )
    assert missing_key.status_code == 422
    assert created.status_code == 201
    assert created.json()["status"] == "active"
    assert invalid.status_code == 422
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"
