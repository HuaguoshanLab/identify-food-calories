"""Public role endpoint keeps authorization and command validation server-side."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.admin.api import get_admin_service
from app.admin.schemas import RecipeCandidateRoleResponse
from app.admin.service import AdminPermissionDenied, RecipeCandidateConflict
from app.agent.graph import NoopAgentRuntimeFactory
from app.auth.api import get_authenticated_principal
from app.main import create_app


@pytest.mark.parametrize("failure,status", [(None, 200), (AdminPermissionDenied(), 403), (KeyError(), 404), (RecipeCandidateConflict(), 409)])
def test_role_endpoint_routes_and_translates_domain_errors(failure, status):
    class Service:
        def change_recipe_candidate_role(self, **kwargs):
            if failure is not None:
                raise failure
            assert kwargs["command"].meal_role == "vegetable"
            return RecipeCandidateRoleResponse(changed_count=1)
    app = create_app(runtime_factory=NoopAgentRuntimeFactory())
    app.dependency_overrides[get_authenticated_principal] = lambda: uuid4()
    app.dependency_overrides[get_admin_service] = Service
    payload = dict(ids=[str(uuid4())], meal_role="vegetable", reason="明确角色", confirm=True)
    with TestClient(app) as client:
        assert client.post('/api/v1/admin/recipe-candidates/meal-role', json=payload).status_code == 422
        response = client.post('/api/v1/admin/recipe-candidates/meal-role', json=payload, headers={"Idempotency-Key": "recipe-role-00000001"})
        assert response.status_code == status
        if status == 200:
            assert response.json() == {"changed_count": 1}
