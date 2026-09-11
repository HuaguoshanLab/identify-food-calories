"""Explicit operational CLI for audited administrator role elevation."""

from __future__ import annotations

import argparse
import sys
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager

from sqlalchemy.orm import Session

from app.admin.repository import SqlAlchemyAdminRepository
from app.admin.service import AdminRoleChangeDenied, AdminService, CatalogVectorSpaceBuildConflict
from app.admin.schemas import CatalogVectorSpaceBuildCommand
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
            if arguments.command == "bootstrap":
                target = repository.get_user_by_email(_normalize_email(arguments.email))
                if target is None:
                    return _denied("target user was not found")
                audit = service.bootstrap_first_admin(
                    target_user_id=target.id, reason=arguments.reason
                )
            elif arguments.command == "promote":
                target = repository.get_user_by_email(_normalize_email(arguments.email))
                if target is None:
                    return _denied("target user was not found")
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
            else:
                build = service.create_catalog_vector_space_build(
                    actor_user_id=arguments.actor_user_id,
                    command=CatalogVectorSpaceBuildCommand(
                        embedding_model="phase063-fake-embedding-v1",
                        embedding_dimension=1024,
                        adapter_version="phase063-eval",
                        retrieval_version="retrieval-06-3-v1",
                        reason=arguments.reason,
                        confirm=True,
                    ),
                    command_key=arguments.idempotency_key,
                )
        except (AdminRoleChangeDenied, CatalogVectorSpaceBuildConflict, PermissionError) as error:
            return _denied(str(error))

    if arguments.command == "vector-build":
        print(f"{build.id} {build.vector_space_id}")
    else:
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
    build = commands.add_parser("vector-build", help="freeze the fixed Phase 06.3 vector build through AdminService")
    build.add_argument("--actor-user-id", type=uuid.UUID, required=True)
    build.add_argument("--reason", required=True)
    build.add_argument("--idempotency-key", required=True)
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
