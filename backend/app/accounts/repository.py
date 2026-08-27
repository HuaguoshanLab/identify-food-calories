"""SQLAlchemy adapter for account recovery; the service owns commit and rollback."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth.models import AuthSession, RefreshToken, User, VerificationChallenge


class SqlAlchemyAccountRecoveryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        return self._session.get(User, user_id)

    def get_user_by_email(self, normalized_email: str) -> User | None:
        return self._session.scalar(select(User).where(User.email == normalized_email))

    def add_challenge(self, challenge: VerificationChallenge) -> VerificationChallenge:
        self._session.add(challenge)
        self._session.flush()
        return challenge

    def get_current_challenge_for_update(
        self, *, context_digest: str, purpose: str
    ) -> VerificationChallenge | None:
        return self._session.scalar(
            select(VerificationChallenge)
            .where(
                VerificationChallenge.context_digest == context_digest,
                VerificationChallenge.purpose == purpose,
                VerificationChallenge.consumed_at.is_(None),
                VerificationChallenge.invalidated_at.is_(None),
            )
            .with_for_update()
        )

    def get_current_challenge_for_user_for_update(
        self, *, user_id: uuid.UUID, purpose: str
    ) -> VerificationChallenge | None:
        return self._session.scalar(
            select(VerificationChallenge)
            .where(
                VerificationChallenge.user_id == user_id,
                VerificationChallenge.purpose == purpose,
                VerificationChallenge.consumed_at.is_(None),
                VerificationChallenge.invalidated_at.is_(None),
            )
            .with_for_update()
        )

    def revoke_all_session_families(
        self, *, user_id: uuid.UUID, revoked_at: datetime
    ) -> None:
        # A password change invalidates every bearer lineage, not merely the browser
        # currently submitting the reset. Both updates share the service transaction.
        session_ids = select(AuthSession.id).where(AuthSession.user_id == user_id)
        self._session.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=revoked_at)
        )
        self._session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.session_id.in_(session_ids),
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )
        self._session.flush()
