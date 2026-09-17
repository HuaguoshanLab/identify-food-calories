from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from app.admin.api import get_admin_service
from app.admin.schemas import RecipeClassificationResponse, RecipeClassificationPreview
from app.admin.recipe_classification import classify_recipe
from app.admin.service import AdminPermissionDenied, RecipeCandidateConflict
from app.agent.graph import NoopAgentRuntimeFactory
from app.auth.api import get_authenticated_principal
from app.main import create_app


@pytest.mark.parametrize(
    "failure,status",
    [
        (None, 200),
        (AdminPermissionDenied(), 403),
        (KeyError(), 404),
        (RecipeCandidateConflict(), 409),
    ],
)
@pytest.mark.parametrize("endpoint", ["classification-backfill", "classification-review"])
def test_backfill_http_contract(failure, status, endpoint):
    class Service:
        def backfill_recipe_classification(self, **kwargs):
            if failure is not None:
                raise failure
            assert kwargs["command"].entries[0].classification.role == "staple"
            return RecipeClassificationResponse(changed_count=1)

    app = create_app(runtime_factory=NoopAgentRuntimeFactory())
    app.dependency_overrides[get_authenticated_principal] = lambda: uuid4()
    app.dependency_overrides[get_admin_service] = Service
    data = dict(
        entries=[
            dict(
                id=str(uuid4()),
                revision=1,
                catalog_food_name="白米饭",
                classification=classify_recipe("白米饭").model_dump(
                    mode="json"
                ),
            )
        ],
        reason="核查",
        confirm=True,
    )
    with TestClient(app) as client:
        assert (
            client.post(
                f"/api/v1/admin/recipe-candidates/{endpoint}", json=data
            ).status_code
            == 422
        )
        assert (
            client.post(
                f"/api/v1/admin/recipe-candidates/{endpoint}",
                json=data,
                headers={"Idempotency-Key": "classification-api-test"},
            ).status_code
            == status
        )


def test_preview_has_no_confirmation_or_write():
    class Service:
        def preview_recipe_classification(self, **kwargs):
            return RecipeClassificationPreview(entries=[], skipped_count=1)

    app = create_app(runtime_factory=NoopAgentRuntimeFactory())
    app.dependency_overrides[get_authenticated_principal] = lambda: uuid4()
    app.dependency_overrides[get_admin_service] = Service
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/admin/recipe-candidates/classification-preview",
            json={"ids": [str(uuid4())]},
        )
        assert response.status_code == 200 and response.json()["skipped_count"] == 1
