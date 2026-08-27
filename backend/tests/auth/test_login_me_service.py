"""Authentication service contracts without HTTP, SQLAlchemy, or network dependencies."""

from __future__ import annotations

import base64
import json
import uuid
from datetime import UTC, datetime

import pytest

from app.auth.models import AuthSession, RefreshToken, User, UserRole
from app.auth.security import hash_password
from app.auth.service import (
    AuthenticatedUserUnavailable,
    AuthenticationService,
    InvalidCredentials,
)


NOW = datetime(2026, 8, 27, 8, 0, tzinfo=UTC)
SECRET = "service-test-secret-with-at-least-32-bytes"


class FakeAuthRepository:
    def __init__(self, users: list[User]) -> None:
        self.users = {user.id: user for user in users}
        self.sessions: list[AuthSession] = []
        self.refresh_tokens: list[RefreshToken] = []

    def get_user_by_email(self, normalized_email: str) -> User | None:
        return next(
            (user for user in self.users.values() if user.email == normalized_email),
            None,
        )

    def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.users.get(user_id)

    def add_session(self, auth_session: AuthSession) -> AuthSession:
        self.sessions.append(auth_session)
        return auth_session

    def add_refresh_token(self, refresh_token: RefreshToken) -> RefreshToken:
        self.refresh_tokens.append(refresh_token)
        return refresh_token


def _user(
    *,
    verified: bool = True,
    active: bool = True,
    role: str = UserRole.USER.value,
) -> User:
    return User(
        id=uuid.uuid4(),
        email="person@example.com",
        password_hash=hash_password("correct horse battery staple"),
        role=role,
        is_active=active,
        email_verified_at=NOW if verified else None,
        created_at=NOW,
        updated_at=NOW,
    )


def _service(
    repository: FakeAuthRepository,
    *,
    commit: list[bool] | None = None,
) -> AuthenticationService:
    return AuthenticationService(
        repository=repository,
        secret_key=SECRET,
        issuer="food-agent-api",
        audience="food-agent-h5",
        now=lambda: NOW,
        commit=(lambda: commit.append(True)) if commit is not None else None,
    )


@pytest.mark.parametrize(
    ("users", "password"),
    [
        ([], "wrong password value"),
        ([_user()], "wrong password value"),
        ([_user(verified=False, active=False)], "correct horse battery staple"),
        ([_user(verified=True, active=False)], "correct horse battery staple"),
    ],
)
def test_login_uses_one_uniform_failure_without_creating_session(
    users: list[User], password: str
) -> None:
    repository = FakeAuthRepository(users)
    commits: list[bool] = []

    with pytest.raises(InvalidCredentials, match="invalid credentials"):
        _service(repository, commit=commits).login(
            email=" PERSON@example.com ", password=password
        )

    assert repository.sessions == []
    assert repository.refresh_tokens == []
    assert commits == []


def test_login_creates_session_and_minimal_access_and_opaque_refresh_tokens() -> None:
    user = _user()
    repository = FakeAuthRepository([user])
    commits: list[bool] = []

    result = _service(repository, commit=commits).login(
        email="PERSON@example.com", password="correct horse battery staple"
    )

    header, payload, _signature = result.access_token.split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=="))
    protected = json.loads(base64.urlsafe_b64decode(header + "=="))
    assert protected == {"alg": "HS256", "typ": "JWT"}
    assert set(claims) == {"sub", "role", "iat", "exp", "jti", "iss", "aud"}
    assert claims["sub"] == str(user.id)
    assert claims["role"] == UserRole.USER.value
    assert "email" not in claims
    assert result.token_type == "bearer"
    assert result.expires_in == 900
    assert len(result.refresh_token) >= 43
    assert repository.refresh_tokens[0].token_digest != result.refresh_token
    assert result.refresh_token not in repository.refresh_tokens[0].token_digest
    assert repository.sessions[0].user_id == user.id
    assert commits == [True]


def test_current_user_reloads_authoritative_status_and_role_from_repository() -> None:
    user = _user(role=UserRole.USER.value)
    repository = FakeAuthRepository([user])
    service = _service(repository)
    login = service.login(
        email=user.email, password="correct horse battery staple"
    )

    user.role = UserRole.ADMIN.value
    current = service.current_user(login.access_token)
    assert current.email == user.email
    assert current.role == UserRole.ADMIN.value

    user.is_active = False
    with pytest.raises(AuthenticatedUserUnavailable):
        service.current_user(login.access_token)

    user.is_active = True
    repository.users.clear()
    with pytest.raises(AuthenticatedUserUnavailable):
        service.current_user(login.access_token)
