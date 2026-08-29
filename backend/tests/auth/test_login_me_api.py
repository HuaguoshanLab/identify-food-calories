"""HTTP and PostgreSQL evidence for login and database-authoritative current identity."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.testclient import TestClient

from app.auth.api import (
    REFRESH_TOKEN_COOKIE,
    _login_source,
    get_authentication_service,
)
from app.auth.models import User, UserRole
from app.auth.repository import SqlAlchemyAuthRepository
from app.auth.schemas import CurrentUserResponse
from app.auth.security import hash_password, issue_access_token
from app.auth.service import (
    AuthenticatedUserUnavailable,
    AuthenticationService,
    InvalidCredentials,
    LoginRateLimited,
    LoginResult,
)
from app.core.config import Settings
from app.main import create_app


NOW = datetime(2026, 8, 27, 7, 30, tzinfo=UTC)
SECRET = "api-test-secret-with-at-least-forty-eight-bytes-for-hmac"
ISSUER = "food-agent-api"
AUDIENCE = "food-agent-h5"


class StubAuthenticationService:
    def __init__(self, *, reject_login: bool = False, rate_limited: bool = False) -> None:
        self.reject_login = reject_login
        self.rate_limited = rate_limited

    def login(self, *, email: str, password: str, source: str) -> LoginResult:
        assert source
        if self.rate_limited:
            raise LoginRateLimited(123)
        if self.reject_login:
            raise InvalidCredentials("invalid credentials")
        return LoginResult(
            access_token="signed-access-value",
            refresh_token="opaque-refresh-value",
            token_type="bearer",
            expires_in=900,
        )

    def current_user(self, access_token: str) -> CurrentUserResponse:
        if access_token != "valid-access-value":
            raise AuthenticatedUserUnavailable
        return CurrentUserResponse(
            id=uuid.uuid4(),
            email="person@example.com",
            email_verified_at=NOW,
            is_active=True,
            role=UserRole.USER.value,
        )


def _settings(*, cookie_secure: bool = False) -> Settings:
    return Settings(
        app_env="test",
        database_url="postgresql+psycopg://postgres:postgres@localhost:5432/food_agent_dev",
        test_database_url=(
            "postgresql+psycopg://postgres:postgres@localhost:55432/food_agent_test"
        ),
        secret_key=SECRET,
        cookie_secure=cookie_secure,
        cors_origins=["http://localhost:5173"],
        smtp_host="localhost",
        smtp_from_email="noreply@local.test",
        _env_file=None,
    )


def _client(service: object, *, cookie_secure: bool = False) -> TestClient:
    application = create_app(_settings(cookie_secure=cookie_secure))
    application.dependency_overrides[get_authentication_service] = lambda: service
    return TestClient(application)


def test_login_returns_access_json_and_scoped_httponly_refresh_cookie() -> None:
    response = _client(StubAuthenticationService()).post(
        "/api/v1/auth/login",
        json={"email": "person@example.com", "password": "correct horse battery"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "access_token": "signed-access-value",
        "token_type": "bearer",
        "expires_in": 900,
    }
    assert "opaque-refresh-value" not in response.text
    cookie = response.headers["set-cookie"]
    assert f"{REFRESH_TOKEN_COOKIE}=opaque-refresh-value" in cookie
    assert "HttpOnly" in cookie
    assert "Path=/api/v1/auth" in cookie
    assert "SameSite=lax" in cookie
    assert "Secure" not in cookie

    secure_cookie = _client(
        StubAuthenticationService(), cookie_secure=True
    ).post(
        "/api/v1/auth/login",
        json={"email": "person@example.com", "password": "correct horse battery"},
    ).headers["set-cookie"]
    assert "Secure" in secure_cookie


def test_login_failure_is_uniform_and_does_not_leak_submitted_credentials() -> None:
    submitted = "this-password-must-not-leak"
    response = _client(StubAuthenticationService(reject_login=True)).post(
        "/api/v1/auth/login",
        json={"email": "unknown@example.com", "password": submitted},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_FAILED"
    assert set(response.json()["error"]) == {"code", "message", "request_id"}
    assert submitted not in response.text
    assert "unknown@example.com" not in response.text
    assert "set-cookie" not in response.headers


def test_login_rate_limit_has_stable_non_enumerating_error() -> None:
    response = _client(StubAuthenticationService(rate_limited=True)).post(
        "/api/v1/auth/login",
        json={"email": "unknown@example.com", "password": "submitted-secret"},
    )

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"
    assert response.json()["error"]["retry_after"] == 123
    assert "unknown@example.com" not in response.text
    assert "submitted-secret" not in response.text
    assert "set-cookie" not in response.headers


def test_local_loopback_login_source_isolated_by_opaque_principal_digest() -> None:
    first = _login_source(
        raw_source="127.0.0.1",
        normalized_email="first@example.com",
        app_env="local",
    )
    second = _login_source(
        raw_source="127.0.0.1",
        normalized_email="second@example.com",
        app_env="local",
    )

    assert first != second
    assert first.startswith("local-loopback-principal:v1:")
    assert len(first.rsplit(":", maxsplit=1)[-1]) == 64
    assert "@example.com" not in first


@pytest.mark.parametrize("app_env", ["test", "production"])
def test_non_local_runtime_keeps_shared_source_bucket(app_env: str) -> None:
    assert _login_source(
        raw_source="127.0.0.1",
        normalized_email="person@example.com",
        app_env=app_env,
    ) == "127.0.0.1"


def _encoded_token(
    *,
    issuer: str = ISSUER,
    audience: str = AUDIENCE,
    issued_at: datetime = NOW,
    expires_at: datetime | None = None,
    algorithm: str = "HS256",
    token_type: str = "JWT",
    secret: str = SECRET,
    subject: str | None = None,
) -> str:
    return jwt.encode(
        {
            "sub": subject or str(uuid.uuid4()),
            "role": UserRole.USER.value,
            "iat": int(issued_at.timestamp()),
            "exp": int((expires_at or (issued_at + timedelta(minutes=15))).timestamp()),
            "jti": str(uuid.uuid4()),
            "iss": issuer,
            "aud": audience,
        },
        secret,
        algorithm=algorithm,
        headers={"typ": token_type},
    )


@pytest.mark.parametrize(
    "token",
    [
        "not-a-jwt",
        _encoded_token(
            issued_at=NOW - timedelta(minutes=30),
            expires_at=NOW - timedelta(minutes=15),
        ),
        _encoded_token(issuer="wrong-issuer"),
        _encoded_token(audience="wrong-audience"),
        _encoded_token(algorithm="HS384"),
        _encoded_token(token_type="not-access-jwt"),
        _encoded_token(secret="different-signing-secret-with-at-least-forty-eight-bytes"),
        _encoded_token(issued_at=NOW + timedelta(seconds=1)),
        _encoded_token(subject="not-a-uuid"),
    ],
)
def test_users_me_rejects_malformed_expired_or_wrong_envelope(token: str) -> None:
    service = AuthenticationService(
        repository=SqlAlchemyAuthRepositoryPlaceholder(),
        secret_key=SECRET,
        issuer=ISSUER,
        audience=AUDIENCE,
        now=lambda: NOW,
    )
    response = _client(service).get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert token not in response.text


class SqlAlchemyAuthRepositoryPlaceholder:
    """Invalid tokens must fail before any repository method can be reached."""

    def get_user_by_id(self, _user_id: uuid.UUID) -> User | None:
        raise AssertionError("invalid bearer must not query persistence")


class MissingUserRepository:
    def get_user_by_id(self, _user_id: uuid.UUID) -> User | None:
        return None


def test_users_me_requires_bearer_header() -> None:
    response = _client(StubAuthenticationService()).get("/api/v1/users/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_users_me_rejects_a_valid_subject_missing_from_database() -> None:
    service = AuthenticationService(
        repository=MissingUserRepository(),
        secret_key=SECRET,
        issuer=ISSUER,
        audience=AUDIENCE,
        now=lambda: NOW,
    )
    token, _expires_in = issue_access_token(
        secret_key=SECRET,
        user_id=uuid.uuid4(),
        role=UserRole.USER.value,
        issuer=ISSUER,
        audience=AUDIENCE,
        issued_at=NOW,
    )

    response = _client(service).get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_users_me_reloads_role_and_active_state_from_real_postgres(db_session: object) -> None:
    repository = SqlAlchemyAuthRepository(db_session)  # type: ignore[arg-type]
    user = repository.add_user(
        User(
            id=uuid.uuid4(),
            email=f"login-{uuid.uuid4().hex}@example.com",
            password_hash=hash_password("correct horse battery staple"),
            role=UserRole.USER.value,
            is_active=True,
            email_verified_at=NOW,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    db_session.commit()  # type: ignore[attr-defined]
    service = AuthenticationService(
        repository=repository,
        secret_key=SECRET,
        issuer=ISSUER,
        audience=AUDIENCE,
        now=lambda: NOW,
        commit=db_session.commit,  # type: ignore[attr-defined]
        rollback=db_session.rollback,  # type: ignore[attr-defined]
    )
    client = _client(service)

    login = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "correct horse battery staple"},
    )
    assert login.status_code == 200
    access_token = login.json()["access_token"]

    user.role = UserRole.ADMIN.value
    db_session.commit()  # type: ignore[attr-defined]
    current = client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert current.status_code == 200
    assert current.json()["role"] == UserRole.ADMIN.value
    assert current.json()["email"] == user.email

    user.is_active = False
    db_session.commit()  # type: ignore[attr-defined]
    inactive = client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert inactive.status_code == 401
    assert inactive.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_login_me_openapi_has_public_schemas_without_persistence_secrets() -> None:
    document = _client(StubAuthenticationService()).get("/api/openapi.json").json()

    assert "/api/v1/auth/login" in document["paths"]
    assert "/api/v1/users/me" in document["paths"]
    assert document["paths"]["/api/v1/users/me"]["get"]["security"]
    serialized = str(document)
    for forbidden in (
        "password_hash",
        "code_digest",
        "context_digest",
        "token_digest",
        "refresh_token",
    ):
        assert forbidden not in serialized
