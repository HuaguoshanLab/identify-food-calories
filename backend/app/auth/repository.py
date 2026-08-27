"""Synchronous SQLAlchemy adapter; application services own transaction boundaries."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.auth.models import (
    AuthSession,
    LoginAttempt,
    RefreshToken,
    User,
    VerificationChallenge,
)


class SqlAlchemyAuthRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_user(self, user: User) -> User:
        self._session.add(user)
        self._session.flush()
        return user

    def get_login_blocked_until(
        self, *, bucket_digests: tuple[str, ...], now: datetime
    ) -> datetime | None:
        return self._session.scalar(
            select(func.max(LoginAttempt.blocked_until)).where(
                LoginAttempt.bucket_digest.in_(bucket_digests),
                LoginAttempt.blocked_until > now,
            )
        )

    def record_login_failure(
        self,
        *,
        bucket_digests: tuple[str, ...],
        now: datetime,
        threshold: int,
        window: timedelta,
        lockout: timedelta,
    ) -> datetime | None:
        """Atomically advance each bucket using PostgreSQL's row-level conflict lock."""

        blocked_until: datetime | None = None
        for bucket_digest in bucket_digests:
            candidate = self._session.scalar(
                text(
                    """
                    INSERT INTO login_attempts (
                        bucket_digest, failed_attempts, window_started_at,
                        window_expires_at, blocked_until, updated_at
                    ) VALUES (
                        :bucket_digest, 1, :now, :window_expires_at, NULL, :now
                    )
                    ON CONFLICT (bucket_digest) DO UPDATE SET
                        failed_attempts = CASE
                            WHEN login_attempts.window_expires_at <= :now THEN 1
                            ELSE login_attempts.failed_attempts + 1
                        END,
                        window_started_at = CASE
                            WHEN login_attempts.window_expires_at <= :now THEN :now
                            ELSE login_attempts.window_started_at
                        END,
                        window_expires_at = CASE
                            WHEN login_attempts.window_expires_at <= :now
                                THEN :window_expires_at
                            ELSE login_attempts.window_expires_at
                        END,
                        blocked_until = CASE
                            WHEN login_attempts.window_expires_at <= :now THEN NULL
                            WHEN login_attempts.blocked_until > :now
                                THEN login_attempts.blocked_until
                            WHEN login_attempts.failed_attempts + 1 >= :threshold
                                THEN :blocked_until
                            ELSE NULL
                        END,
                        updated_at = :now
                    RETURNING blocked_until
                    """
                ),
                {
                    "bucket_digest": bucket_digest,
                    "now": now,
                    "window_expires_at": now + window,
                    "threshold": threshold,
                    "blocked_until": now + lockout,
                },
            )
            if candidate is not None and (
                blocked_until is None or candidate > blocked_until
            ):
                blocked_until = candidate
        return blocked_until

    def reset_login_attempts(self, *, bucket_digests: tuple[str, ...]) -> None:
        self._session.execute(
            delete(LoginAttempt).where(LoginAttempt.bucket_digest.in_(bucket_digests))
        )

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
        statement = (
            select(VerificationChallenge)
            .where(
                VerificationChallenge.context_digest == context_digest,
                VerificationChallenge.purpose == purpose,
                VerificationChallenge.consumed_at.is_(None),
                VerificationChallenge.invalidated_at.is_(None),
            )
            .with_for_update()
        )
        return self._session.scalar(statement)

    def get_current_challenge_for_user_for_update(
        self, *, user_id: uuid.UUID, purpose: str
    ) -> VerificationChallenge | None:
        statement = (
            select(VerificationChallenge)
            .where(
                VerificationChallenge.user_id == user_id,
                VerificationChallenge.purpose == purpose,
                VerificationChallenge.consumed_at.is_(None),
                VerificationChallenge.invalidated_at.is_(None),
            )
            .with_for_update()
        )
        return self._session.scalar(statement)

    def add_session(self, auth_session: AuthSession) -> AuthSession:
        self._session.add(auth_session)
        self._session.flush()
        return auth_session

    def get_session_for_user(
        self, *, session_id: uuid.UUID, user_id: uuid.UUID
    ) -> AuthSession | None:
        return self._session.scalar(
            select(AuthSession).where(
                AuthSession.id == session_id,
                AuthSession.user_id == user_id,
            )
        )

    def get_session_for_update(self, session_id: uuid.UUID) -> AuthSession | None:
        return self._session.scalar(
            select(AuthSession).where(AuthSession.id == session_id).with_for_update()
        )

    def list_sessions_for_user(self, user_id: uuid.UUID) -> list[AuthSession]:
        return list(
            self._session.scalars(
                select(AuthSession)
                .where(AuthSession.user_id == user_id)
                .order_by(AuthSession.created_at.desc())
            )
        )

    def revoke_session_for_user(
        self, *, session_id: uuid.UUID, user_id: uuid.UUID, revoked_at: datetime
    ) -> bool:
        result = self._session.execute(
            update(AuthSession)
            .where(
                AuthSession.id == session_id,
                AuthSession.user_id == user_id,
                AuthSession.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )
        # Session.execute is typed as a generic Result; UPDATE's affected-row
        # count is the atomic ownership proof required by this authorization check.
        return cast(CursorResult[Any], result).rowcount == 1

    def revoke_session_family(
        self, *, session_id: uuid.UUID, revoked_at: datetime
    ) -> None:
        self._session.execute(
            update(AuthSession)
            .where(AuthSession.id == session_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=revoked_at)
        )
        self._session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.session_id == session_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )
        self._session.flush()

    def add_refresh_token(self, refresh_token: RefreshToken) -> RefreshToken:
        self._session.add(refresh_token)
        self._session.flush()
        return refresh_token

    def get_refresh_token_for_update(self, token_digest: str) -> RefreshToken | None:
        return self._session.scalar(
            select(RefreshToken)
            .where(RefreshToken.token_digest == token_digest)
            .with_for_update()
        )
