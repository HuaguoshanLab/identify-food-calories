"""Refresh rotation and user-scoped session service contracts."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.auth.models import AuthSession, RefreshToken, User, UserRole
from app.auth.security import digest_refresh_token
from app.auth.service import (
    AuthenticationService,
    CurrentSessionCannotBeRevoked,
    InvalidRefreshToken,
    RefreshTokenReplayed,
)


NOW = datetime(2026, 8, 27, 9, 30, tzinfo=UTC)
SECRET = "refresh-service-test-secret-with-at-least-forty-eight-bytes"


class FakeRefreshRepository:
    def __init__(self, *, user: User, session: AuthSession, token: RefreshToken) -> None:
        self.user = user
        self.sessions = {session.id: session}
        self.tokens = {token.token_digest: token}
        self.created_tokens: list[RefreshToken] = []
        self.family_revocations: list[uuid.UUID] = []

    def get_refresh_token_for_update(self, token_digest: str) -> RefreshToken | None:
        return self.tokens.get(token_digest)

    def add_refresh_token(self, refresh_token: RefreshToken) -> RefreshToken:
        self.created_tokens.append(refresh_token)
        self.tokens[refresh_token.token_digest] = refresh_token
        return refresh_token

    def get_session_for_user(
        self, *, session_id: uuid.UUID, user_id: uuid.UUID
    ) -> AuthSession | None:
        session = self.sessions.get(session_id)
        return session if session is not None and session.user_id == user_id else None

    def list_sessions_for_user(self, user_id: uuid.UUID) -> list[AuthSession]:
        return [session for session in self.sessions.values() if session.user_id == user_id]

    def revoke_session_for_user(
        self, *, session_id: uuid.UUID, user_id: uuid.UUID, revoked_at: datetime
    ) -> bool:
        session = self.get_session_for_user(session_id=session_id, user_id=user_id)
        if session is None:
            return False
        session.revoked_at = revoked_at
        return True

    def revoke_session_family(
        self, *, session_id: uuid.UUID, revoked_at: datetime
    ) -> None:
        self.family_revocations.append(session_id)
        session = self.sessions[session_id]
        session.revoked_at = revoked_at
        for token in self.tokens.values():
            if token.session_id == session_id:
                token.revoked_at = revoked_at

    def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.user if user_id == self.user.id else None


def _fixture() -> tuple[FakeRefreshRepository, AuthenticationService, str, AuthSession]:
    user = User(
        id=uuid.uuid4(),
        email="refresh@example.com",
        password_hash="unused",
        role=UserRole.USER.value,
        is_active=True,
        email_verified_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )
    session = AuthSession(
        id=uuid.uuid4(),
        user_id=user.id,
        created_at=NOW,
        expires_at=NOW + timedelta(days=30),
        revoked_at=None,
        device_label=None,
    )
    raw_token = "opaque-refresh-token"
    token = RefreshToken(
        id=uuid.uuid4(),
        session_id=session.id,
        token_digest=digest_refresh_token(secret_key=SECRET, refresh_token=raw_token),
        issued_at=NOW,
        expires_at=NOW + timedelta(days=30),
        consumed_at=None,
        revoked_at=None,
    )
    repository = FakeRefreshRepository(user=user, session=session, token=token)
    commits: list[bool] = []
    service = AuthenticationService(
        repository=repository,
        secret_key=SECRET,
        issuer="food-agent-api",
        audience="food-agent-h5",
        now=lambda: NOW,
        refresh_token_factory=lambda: "rotated-opaque-refresh-token",
        commit=lambda: commits.append(True),
    )
    return repository, service, raw_token, session


def test_refresh_consumes_digest_once_and_returns_only_successor_secret() -> None:
    repository, service, raw_token, session = _fixture()

    result = service.refresh(raw_token)

    old = repository.tokens[digest_refresh_token(secret_key=SECRET, refresh_token=raw_token)]
    assert old.consumed_at == NOW
    assert len(repository.created_tokens) == 1
    successor = repository.created_tokens[0]
    assert successor.session_id == session.id
    assert successor.token_digest != "rotated-opaque-refresh-token"
    assert result.refresh_token == "rotated-opaque-refresh-token"
    assert result.refresh_token not in repr(successor)


def test_replay_revokes_entire_session_family_before_rejecting() -> None:
    repository, service, raw_token, session = _fixture()
    service.refresh(raw_token)

    with pytest.raises(RefreshTokenReplayed):
        service.refresh(raw_token)

    assert repository.family_revocations == [session.id]
    assert repository.sessions[session.id].revoked_at == NOW
    assert all(token.revoked_at == NOW for token in repository.tokens.values())


def test_refresh_rejects_unknown_or_revoked_token_without_minting_successor() -> None:
    repository, service, _raw_token, session = _fixture()
    session.revoked_at = NOW

    with pytest.raises(InvalidRefreshToken):
        service.refresh("unknown-token")

    assert repository.created_tokens == []


def test_logout_and_session_listing_are_scoped_to_authenticated_user() -> None:
    repository, service, _raw_token, session = _fixture()
    other = AuthSession(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        created_at=NOW,
        expires_at=NOW + timedelta(days=30),
        revoked_at=None,
        device_label=None,
    )
    repository.sessions[other.id] = other

    sessions = service.list_sessions(user_id=repository.user.id, current_session_id=session.id)
    assert [item.id for item in sessions] == [session.id]

    assert service.logout(user_id=repository.user.id, session_id=session.id) is True
    assert session.revoked_at == NOW
    assert service.logout(user_id=repository.user.id, session_id=other.id) is False
    assert other.revoked_at is None


def test_current_session_cannot_be_revoked_through_session_management() -> None:
    repository, service, _raw_token, session = _fixture()

    with pytest.raises(CurrentSessionCannotBeRevoked):
        service.revoke_session(
            user_id=repository.user.id,
            session_id=session.id,
            current_session_id=session.id,
        )

