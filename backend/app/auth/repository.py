"""Synchronous SQLAlchemy adapter; application services own transaction boundaries."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import AuthSession, RefreshToken, User, VerificationChallenge


class SqlAlchemyAuthRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_user(self, user: User) -> User:
        self._session.add(user)
        self._session.flush()
        return user

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

    def list_sessions_for_user(self, user_id: uuid.UUID) -> list[AuthSession]:
        return list(
            self._session.scalars(
                select(AuthSession)
                .where(AuthSession.user_id == user_id)
                .order_by(AuthSession.created_at.desc())
            )
        )

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
