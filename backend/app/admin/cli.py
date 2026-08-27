"""Explicit operational CLI for audited administrator role elevation."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from contextlib import AbstractContextManager

from sqlalchemy.orm import Session

from app.admin.repository import SqlAlchemyAdminRepository
from app.admin.service import AdminRoleChangeDenied, AdminService
from app.core.database import create_session_factory


def main(
    argv: list[str] | None = None,
    *,
    session_factory: Callable[[], AbstractContextManager[Session]] | None = None,
) -> int:
    """Run one explicit admin transition; normal application requests cannot call this."""

    arguments = _parser().parse_args(argv)
    factory = session_factory or create_session_factory()
    with factory() as session:
        repository = SqlAlchemyAdminRepository(session)
        service = AdminService(
            repository=repository, commit=session.commit, rollback=session.rollback
        )
        try:
            target = repository.get_user_by_email(_normalize_email(arguments.email))
            if target is None:
                return _denied("target user was not found")
            if arguments.command == "bootstrap":
                audit = service.bootstrap_first_admin(
                    target_user_id=target.id, reason=arguments.reason
                )
            else:
                actor = repository.get_user_by_email(
                    _normalize_email(arguments.actor_email)
                )
                if actor is None:
                    return _denied("actor user was not found")
                audit = service.promote_admin(
                    actor_user_id=actor.id,
                    target_user_id=target.id,
                    reason=arguments.reason,
                )
        except AdminRoleChangeDenied as error:
            return _denied(str(error))

    print(f"admin role change recorded: {audit.id}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bootstrap or promote an administrator with required audit evidence."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    bootstrap = commands.add_parser("bootstrap", help="create the first active admin")
    bootstrap.add_argument("--email", required=True, help="existing target account email")
    bootstrap.add_argument("--reason", required=True, help="non-empty audit reason")
    promote = commands.add_parser("promote", help="promote with an existing admin actor")
    promote.add_argument("--actor-email", required=True, help="verified active admin email")
    promote.add_argument("--email", required=True, help="existing target account email")
    promote.add_argument("--reason", required=True, help="non-empty audit reason")
    return parser


def _normalize_email(email: str) -> str:
    value = email.strip().lower()
    if not value:
        raise AdminRoleChangeDenied("email must not be empty")
    return value


def _denied(message: str) -> int:
    print(f"admin role change denied: {message}", file=sys.stderr)
    return 2


if __name__ == "__main__":  # pragma: no cover - the console entry invokes main().
    raise SystemExit(main())
