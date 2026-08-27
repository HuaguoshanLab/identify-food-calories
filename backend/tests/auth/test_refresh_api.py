"""HTTP contracts for refresh, logout, and user-scoped session management."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.auth.api import (
    REFRESH_TOKEN_COOKIE,
    get_authentication_service,
)
from app.auth.schemas import AccessTokenResponse, SessionResponse
from app.auth.service import (
    CurrentSessionCannotBeRevoked,
    InvalidRefreshToken,
    LoginResult,
    RefreshTokenReplayed,
)
from app.core.config import Settings
from app.main import create_app


NOW = datetime(2026, 8, 27, 9, 30, tzinfo=UTC)


class StubRefreshService:
    def __init__(self) -> None:
        self.user_id = uuid.uuid4()
        self.session_id = uuid.uuid4()
        self.deleted: list[uuid.UUID] = []

    def refresh(self, refresh_token: str) -> LoginResult:
        assert refresh_token == "old-opaque-value"
        return LoginResult(
            access_token="new-signed-access-value",
            refresh_token="new-opaque-refresh-value",
            token_type="bearer",
            expires_in=900,
        )

    def authenticated_session(self, access_token: str) -> tuple[uuid.UUID, uuid.UUID]:
        assert access_token == "valid-access-value"
        return self.user_id, self.session_id

    def logout(self, *, user_id: uuid.UUID, session_id: uuid.UUID) -> bool:
        assert user_id == self.user_id and session_id == self.session_id
        return True

    def list_sessions(
        self, *, user_id: uuid.UUID, current_session_id: uuid.UUID
    ) -> list[SessionResponse]:
        assert user_id == self.user_id and current_session_id == self.session_id
        return [
            SessionResponse(
                id=self.session_id,
                created_at=NOW,
                last_seen_at=NOW,
                expires_at=NOW,
                revoked_at=None,
                device_label=None,
                is_current=True,
            )
        ]

    def revoke_session(
        self, *, user_id: uuid.UUID, session_id: uuid.UUID, current_session_id: uuid.UUID
    ) -> bool:
        assert user_id == self.user_id and current_session_id == self.session_id
        self.deleted.append(session_id)
        if session_id == current_session_id:
            raise CurrentSessionCannotBeRevoked
        return False


def _client(service: object, *, cookie_secure: bool = False) -> TestClient:
    application = create_app(
        Settings(
            app_env="test",
            database_url="postgresql+psycopg://postgres:postgres@localhost:5432/food_agent_dev",
            test_database_url="postgresql+psycopg://postgres:postgres@localhost:55432/food_agent_test",
            secret_key="refresh-api-test-secret-with-at-least-forty-eight-bytes",
            cookie_secure=cookie_secure,
            cors_origins=["http://localhost:5173"],
            smtp_host="localhost",
            smtp_from_email="noreply@local.test",
            _env_file=None,
        )
    )
    application.dependency_overrides[get_authentication_service] = lambda: service
    return TestClient(application)


def test_refresh_rotates_httponly_cookie_without_exposing_refresh_secret() -> None:
    response = _client(StubRefreshService()).post(
        "/api/v1/auth/refresh", cookies={REFRESH_TOKEN_COOKIE: "old-opaque-value"}
        , headers={"Origin": "http://localhost:5173"}
    )

    assert response.status_code == 200
    assert response.json() == AccessTokenResponse(
        access_token="new-signed-access-value", token_type="bearer", expires_in=900
    ).model_dump()
    assert "old-opaque-value" not in response.text
    assert "new-opaque-refresh-value" not in response.text
    cookie = response.headers["set-cookie"]
    assert f"{REFRESH_TOKEN_COOKIE}=new-opaque-refresh-value" in cookie
    assert "HttpOnly" in cookie and "Path=/api/v1/auth" in cookie and "SameSite=lax" in cookie


def test_refresh_requires_origin_or_referer_that_matches_exact_cors_origin() -> None:
    client = _client(StubRefreshService())

    rejected = client.post(
        "/api/v1/auth/refresh",
        cookies={REFRESH_TOKEN_COOKIE: "old-opaque-value"},
        headers={"Origin": "https://attacker.example"},
    )
    allowed = client.post(
        "/api/v1/auth/refresh",
        cookies={REFRESH_TOKEN_COOKIE: "old-opaque-value"},
        headers={"Origin": "http://localhost:5173"},
    )

    assert rejected.status_code == 403
    assert rejected.json()["error"]["code"] == "CSRF_ORIGIN_INVALID"
    assert allowed.status_code == 200


def test_refresh_replay_and_missing_cookie_use_stable_errors_and_clear_cookie() -> None:
    class ReplayService(StubRefreshService):
        def refresh(self, refresh_token: str) -> LoginResult:
            raise RefreshTokenReplayed

    missing = _client(StubRefreshService()).post("/api/v1/auth/refresh")
    replay = _client(ReplayService()).post(
        "/api/v1/auth/refresh",
        cookies={REFRESH_TOKEN_COOKIE: "old-opaque-value"},
    )

    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "REFRESH_TOKEN_INVALID"
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "REFRESH_TOKEN_INVALID"
    assert "Max-Age=0" in replay.headers["set-cookie"]


def test_logout_list_and_delete_sessions_require_bearer_and_never_allow_current_delete() -> None:
    service = StubRefreshService()
    client = _client(service)
    headers = {"Authorization": "Bearer valid-access-value", "Origin": "http://localhost:5173"}

    sessions = client.get("/api/v1/auth/sessions", headers=headers)
    logout = client.post("/api/v1/auth/logout", headers=headers)
    current_delete = client.delete(f"/api/v1/auth/sessions/{service.session_id}", headers=headers)

    assert sessions.status_code == 200
    assert sessions.json()[0]["is_current"] is True
    assert logout.status_code == 204
    assert "Max-Age=0" in logout.headers["set-cookie"]
    assert current_delete.status_code == 409
    assert current_delete.json()["error"]["code"] == "CURRENT_SESSION_REQUIRES_LOGOUT"


def test_refresh_and_session_openapi_never_publish_refresh_cookie_or_digest() -> None:
    document = _client(StubRefreshService()).get("/api/openapi.json").json()
    serialized = str(document)

    assert {"/api/v1/auth/refresh", "/api/v1/auth/logout", "/api/v1/auth/sessions"}.issubset(document["paths"])
    assert "refresh_token" not in serialized
    assert "token_digest" not in serialized
