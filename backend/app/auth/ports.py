"""Persistence capability required by auth services, independent of SQLAlchemy Session."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Protocol

from app.auth.models import AuthSession, RefreshToken, User, VerificationChallenge


class AuthRepository(Protocol):
    def get_login_blocked_until(
        self, *, bucket_digests: tuple[str, ...], now: datetime
    ) -> datetime | None: ...

    def record_login_failure(
        self,
        *,
        bucket_digests: tuple[str, ...],
        now: datetime,
        threshold: int,
        window: timedelta,
        lockout: timedelta,
    ) -> datetime | None: ...

    def reset_login_attempts(self, *, bucket_digests: tuple[str, ...]) -> None: ...

    def add_user(self, user: User) -> User: ...

    def get_user_by_id(self, user_id: uuid.UUID) -> User | None: ...

    def get_user_by_email(self, normalized_email: str) -> User | None: ...

    def add_challenge(self, challenge: VerificationChallenge) -> VerificationChallenge: ...

    def get_current_challenge_for_update(
        self, *, context_digest: str, purpose: str
    ) -> VerificationChallenge | None: ...

    def get_current_challenge_for_user_for_update(
        self, *, user_id: uuid.UUID, purpose: str
    ) -> VerificationChallenge | None: ...

    def add_session(self, auth_session: AuthSession) -> AuthSession: ...

    def get_session_for_user(
        self, *, session_id: uuid.UUID, user_id: uuid.UUID
    ) -> AuthSession | None: ...

    def get_session_for_update(self, session_id: uuid.UUID) -> AuthSession | None: ...

    def list_sessions_for_user(self, user_id: uuid.UUID) -> list[AuthSession]: ...

    def revoke_session_for_user(
        self, *, session_id: uuid.UUID, user_id: uuid.UUID, revoked_at: datetime
    ) -> bool: ...

    def revoke_session_family(
        self, *, session_id: uuid.UUID, revoked_at: datetime
    ) -> None: ...

    def add_refresh_token(self, refresh_token: RefreshToken) -> RefreshToken: ...

    def get_refresh_token_for_update(self, token_digest: str) -> RefreshToken | None: ...
