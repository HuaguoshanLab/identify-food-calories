"""Persistence capability required by auth services, independent of SQLAlchemy Session."""

from __future__ import annotations

import uuid
from typing import Protocol

from app.auth.models import AuthSession, RefreshToken, User, VerificationChallenge


class AuthRepository(Protocol):
    def add_user(self, user: User) -> User: ...

    def get_user_by_id(self, user_id: uuid.UUID) -> User | None: ...

    def get_user_by_email(self, normalized_email: str) -> User | None: ...

    def add_challenge(self, challenge: VerificationChallenge) -> VerificationChallenge: ...

    def get_current_challenge_for_update(
        self, *, context_digest: str, purpose: str
    ) -> VerificationChallenge | None: ...

    def add_session(self, auth_session: AuthSession) -> AuthSession: ...

    def get_session_for_user(
        self, *, session_id: uuid.UUID, user_id: uuid.UUID
    ) -> AuthSession | None: ...

    def list_sessions_for_user(self, user_id: uuid.UUID) -> list[AuthSession]: ...

    def add_refresh_token(self, refresh_token: RefreshToken) -> RefreshToken: ...

    def get_refresh_token_for_update(self, token_digest: str) -> RefreshToken | None: ...
