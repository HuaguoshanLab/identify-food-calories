"""Create the one fixed local-development administrator without committing credentials.

This is a bounded workstation setup step, not a production bootstrap path.  It only
accepts the conventional loopback development database and relies on an ignored .env
file for the password so a repository checkout never contains a reusable credential.
"""

from __future__ import annotations

import sys
import uuid
from datetime import UTC, datetime

from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.admin.repository import SqlAlchemyAdminRepository
from app.admin.service import AdminService, AdminRoleChangeDenied
from app.auth.models import User, UserRole
from app.auth.schemas import RegisterRequest
from app.auth.security import hash_password
from app.core.config import ConfigurationError, Settings, runtime_database_url
from app.core.database import create_session_factory


LOCAL_BOOTSTRAP_REASON = "local development administrator bootstrap"
LOCAL_BOOTSTRAP_ADMIN_EMAIL = "admin@admin.com"


def guarded_local_settings() -> Settings:
    """Reject every target except the conventional local development database."""

    settings = Settings()
    if settings.app_env != "local":
        raise ConfigurationError("local admin bootstrap requires APP_ENV=local")
    database = make_url(runtime_database_url(settings))
    if database.host not in {"localhost", "127.0.0.1", "::1"}:
        raise ConfigurationError("local admin bootstrap requires a loopback PostgreSQL host")
    if database.database != "food_agent_dev":
        raise ConfigurationError("local admin bootstrap requires the food_agent_dev database")
    if (
        settings.local_bootstrap_admin_password is None
        or not settings.local_bootstrap_admin_password.get_secret_value()
    ):
        raise ConfigurationError("LOCAL_BOOTSTRAP_ADMIN_PASSWORD is required locally")
    return settings


def ensure_local_admin(
    session: Session, *, email: str, password: str, now: datetime | None = None
) -> bool:
    """Create and audit the fixed local admin once; never reset an existing account."""

    credentials = RegisterRequest(email=email, password=password)
    repository = SqlAlchemyAdminRepository(session)
    existing = repository.get_user_by_email(credentials.email.strip().lower())
    if existing is not None:
        if (
            existing.role == UserRole.ADMIN.value
            and existing.is_active
            and existing.email_verified_at is not None
        ):
            return False
        raise ConfigurationError("the configured local admin email is already in use")

    occurred_at = now or datetime.now(UTC)
    target = User(
        id=uuid.uuid4(),
        email=credentials.email.strip().lower(),
        password_hash=hash_password(credentials.password),
        role=UserRole.USER.value,
        is_active=True,
        email_verified_at=occurred_at,
        created_at=occurred_at,
        updated_at=occurred_at,
    )
    session.add(target)
    session.flush()
    AdminService(
        repository=repository,
        commit=session.commit,
        rollback=session.rollback,
        now=lambda: occurred_at,
    ).bootstrap_first_admin(target_user_id=target.id, reason=LOCAL_BOOTSTRAP_REASON)
    return True


def main() -> int:
    try:
        settings = guarded_local_settings()
        password = settings.local_bootstrap_admin_password
        assert password is not None
        with create_session_factory(settings)() as session:
            created = ensure_local_admin(
                session,
                email=LOCAL_BOOTSTRAP_ADMIN_EMAIL,
                password=password.get_secret_value(),
            )
        print("local administrator created" if created else "local administrator already exists")
        return 0
    except (AdminRoleChangeDenied, ConfigurationError, SQLAlchemyError, ValueError):
        print("local administrator bootstrap failed", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
