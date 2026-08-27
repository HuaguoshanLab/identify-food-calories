"""Persistence capabilities for password recovery, independent of SQLAlchemy."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from app.auth.models import User, VerificationChallenge


class AccountRecoveryRepository(Protocol):
    def get_user_by_id(self, user_id: uuid.UUID) -> User | None: ...

    def get_user_by_email(self, normalized_email: str) -> User | None: ...

    def add_challenge(self, challenge: VerificationChallenge) -> VerificationChallenge: ...

    def get_current_challenge_for_update(
        self, *, context_digest: str, purpose: str
    ) -> VerificationChallenge | None: ...

    def get_current_challenge_for_user_for_update(
        self, *, user_id: uuid.UUID, purpose: str
    ) -> VerificationChallenge | None: ...


class SessionFamilyRevoker(Protocol):
    """Revoke every active family for a user through the request's DB transaction."""

    def revoke_all_session_families(
        self, *, user_id: uuid.UUID, revoked_at: datetime
    ) -> None: ...
