"""SQLAlchemy adapter for admin role reads, locks, and audit insertion."""

from __future__ import annotations

import uuid

from sqlalchemy import exists, select, text
from sqlalchemy.orm import Session

from app.admin.models import AdminRoleAudit
from app.auth.models import User, UserRole


class SqlAlchemyAdminRepository:
    """Flush-only persistence adapter; the service owns the transaction boundary."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def acquire_bootstrap_lock(self) -> None:
        """Serialize the one-time bootstrap check without adding mutable global state."""

        self._session.execute(text("SELECT pg_advisory_xact_lock(918273645)"))

    def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        return self._session.get(User, user_id)

    def get_user_by_email(self, normalized_email: str) -> User | None:
        return self._session.scalar(select(User).where(User.email == normalized_email))

    def get_user_for_update(self, user_id: uuid.UUID) -> User | None:
        return self._session.scalar(
            select(User).where(User.id == user_id).with_for_update()
        )

    def has_active_admin(self) -> bool:
        return bool(
            self._session.scalar(
                select(
                    exists().where(
                        User.role == UserRole.ADMIN.value,
                        User.is_active.is_(True),
                    )
                )
            )
        )

    def add_audit(self, audit: AdminRoleAudit) -> AdminRoleAudit:
        self._session.add(audit)
        self._session.flush()
        return audit
