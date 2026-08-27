"""Final Phase 1 public-surface and disclosure contracts."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _client() -> TestClient:
    return TestClient(
        create_app(
            Settings(
                app_env="test",
                database_url="postgresql+psycopg://postgres:postgres@localhost:5432/food_agent_dev",
                test_database_url="postgresql+psycopg://postgres:postgres@localhost:55432/food_agent_test",
                secret_key="phase-one-security-contract-secret-at-least-forty-eight-bytes",
                cors_origins=["http://127.0.0.1:4173"],
                smtp_host="localhost",
                smtp_from_email="noreply@local.test",
                _env_file=None,
            )
        )
    )


def test_openapi_exposes_only_public_auth_shapes_and_never_refresh_internals() -> None:
    document = _client().get("/api/openapi.json").json()
    serialized = str(document).lower()

    assert "/api/v1/users/me" in document["paths"]
    assert "/api/v1/admin/probe" in document["paths"]
    assert "/api/v1/auth/password-recovery/reset" in document["paths"]
    assert "refresh_token" not in serialized
    assert "token_digest" not in serialized
    assert "code_digest" not in serialized
    assert "password_hash" not in serialized


def test_user_spa_has_no_admin_route_or_admin_api_client() -> None:
    app_source = (REPOSITORY_ROOT / "frontend/src/App.tsx").read_text(encoding="utf-8")
    client_source = (REPOSITORY_ROOT / "frontend/src/auth/api.ts").read_text(encoding="utf-8")

    assert 'path="/admin"' not in app_source
    assert "/admin/" not in client_source


def test_auth_and_recovery_sources_do_not_log_raw_credentials_or_secrets() -> None:
    sensitive_sources = [
        *REPOSITORY_ROOT.glob("backend/app/auth/*.py"),
        *REPOSITORY_ROOT.glob("backend/app/accounts/*.py"),
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in sensitive_sources)

    assert "print(" not in combined
    assert "logger.debug(" not in combined
    assert "logger.info(" not in combined
