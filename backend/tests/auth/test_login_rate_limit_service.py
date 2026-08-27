"""Deterministic service contracts for database-authoritative login throttling."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.auth.models import AuthSession, RefreshToken, User, UserRole
from app.auth.security import hash_password
from app.auth.service import AuthenticationService, InvalidCredentials, LoginRateLimited


NOW = datetime(2026, 8, 27, 9, 0, tzinfo=UTC)
SECRET = "rate-limit-test-secret-with-at-least-forty-eight-bytes"


class FakeRateLimitRepository:
    def __init__(self, user: User | None = None) -> None:
        self.user = user
        self.blocked_until: datetime | None = None
        self.checked: list[tuple[tuple[str, ...], datetime]] = []
        self.failures: list[tuple[tuple[str, ...], datetime, int, timedelta, timedelta]] = []
        self.resets: list[tuple[str, ...]] = []
        self.sessions: list[AuthSession] = []
        self.refresh_tokens: list[RefreshToken] = []

    def get_user_by_email(self, normalized_email: str) -> User | None:
        if self.user is not None and self.user.email == normalized_email:
            return self.user
        return None

    def get_login_blocked_until(
        self, *, bucket_digests: tuple[str, ...], now: datetime
    ) -> datetime | None:
        self.checked.append((bucket_digests, now))
        return self.blocked_until

    def record_login_failure(
        self,
        *,
        bucket_digests: tuple[str, ...],
        now: datetime,
        threshold: int,
        window: timedelta,
        lockout: timedelta,
    ) -> datetime | None:
        self.failures.append((bucket_digests, now, threshold, window, lockout))
        return self.blocked_until

    def reset_login_attempts(self, *, bucket_digests: tuple[str, ...]) -> None:
        self.resets.append(bucket_digests)

    def add_session(self, auth_session: AuthSession) -> AuthSession:
        self.sessions.append(auth_session)
        return auth_session

    def add_refresh_token(self, refresh_token: RefreshToken) -> RefreshToken:
        self.refresh_tokens.append(refresh_token)
        return refresh_token


def _user() -> User:
    return User(
        id=uuid.uuid4(),
        email="person@example.com",
        password_hash=hash_password("correct horse battery staple"),
        role=UserRole.USER.value,
        is_active=True,
        email_verified_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )


def _service(repository: FakeRateLimitRepository) -> AuthenticationService:
    return AuthenticationService(
        repository=repository,
        secret_key=SECRET,
        issuer="food-agent-api",
        audience="food-agent-h5",
        now=lambda: NOW,
    )


def test_failed_login_uses_only_hmac_principal_and_source_buckets() -> None:
    repository = FakeRateLimitRepository()

    with pytest.raises(InvalidCredentials):
        _service(repository).login(
            email=" PERSON@Example.com ",
            password="wrong password value",
            source="203.0.113.42",
        )

    checked_buckets, checked_at = repository.checked[0]
    failed_buckets, failed_at, threshold, window, lockout = repository.failures[0]
    assert checked_buckets == failed_buckets
    assert len(checked_buckets) == 2
    assert len(set(checked_buckets)) == 2
    assert all(len(bucket) == 64 for bucket in checked_buckets)
    assert "person@example.com" not in "".join(checked_buckets)
    assert "203.0.113.42" not in "".join(checked_buckets)
    assert checked_at == failed_at == NOW
    assert threshold == 5
    assert window == lockout == timedelta(minutes=5)


def test_preexisting_or_new_threshold_block_returns_one_stable_exception() -> None:
    repository = FakeRateLimitRepository()
    repository.blocked_until = NOW + timedelta(minutes=3)

    with pytest.raises(LoginRateLimited) as blocked:
        _service(repository).login(
            email="unknown@example.com",
            password="wrong password value",
            source="198.51.100.7",
        )

    assert blocked.value.retry_after == 180
    assert repository.failures == []
    assert repository.sessions == []


def test_success_resets_both_buckets_before_committing_session() -> None:
    repository = FakeRateLimitRepository(_user())

    _service(repository).login(
        email="PERSON@example.com",
        password="correct horse battery staple",
        source="192.0.2.9",
    )

    assert len(repository.resets) == 1
    assert repository.resets[0] == repository.checked[0][0]
    assert len(repository.sessions) == 1
    assert len(repository.refresh_tokens) == 1
