"""Public runtime contract for the application foundation."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings


def test_health_endpoint_has_versioned_stable_contract() -> None:
    from app.main import create_app

    settings = Settings(
        app_env="test",
        database_url="postgresql+psycopg://postgres:postgres@localhost:5432/food_agent_dev",
        test_database_url=(
            "postgresql+psycopg://postgres:postgres@localhost:55432/food_agent_test"
        ),
        _env_file=None,
    )
    client = TestClient(create_app(settings))

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "v1"}
