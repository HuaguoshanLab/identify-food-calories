"""Controlled CLI for a hash-bound vector-space activation.

The supplied actor UUID is only a database lookup key.  ``AdminService`` reads
the current role and all mutable proof again; this command cannot turn a claimed
PASS result into authority.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import uuid

from app.admin.repository import SqlAlchemyAdminRepository
from app.admin.service import AdminService, CatalogVectorSpaceActivationConflict
from app.core.database import create_session_factory


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actor = parser.add_mutually_exclusive_group(required=True)
    actor.add_argument("--actor-user-id", type=uuid.UUID)
    actor.add_argument("--actor-email", help="resolve the local operator to a UUID before service RBAC")
    parser.add_argument("--vector-space-id", type=uuid.UUID, required=True)
    parser.add_argument("--build-id", type=uuid.UUID, required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--idempotency-key", required=True)
    parser.add_argument("--release", type=Path, default=Path(__file__).with_name("release.json"))
    arguments = parser.parse_args(sys.argv[1:] if argv is None else argv)
    session_factory = create_session_factory()
    with session_factory() as session:
        repository = SqlAlchemyAdminRepository(session)
        if arguments.actor_user_id is not None:
            actor_user_id = arguments.actor_user_id
        else:
            account = repository.get_user_by_email(_normalize_email(arguments.actor_email))
            if account is None:
                parser.error("actor user was not found")
            # Email only resolves the operator locally. Activation authority is
            # still reloaded and checked by AdminService using this UUID.
            actor_user_id = account.id
        service = AdminService(
            repository=repository,
            commit=session.commit,
            rollback=session.rollback,
        )
        try:
            approval = service.activate_vector_space(
                actor_user_id=actor_user_id,
                vector_space_id=arguments.vector_space_id,
                build_id=arguments.build_id,
                reason=arguments.reason,
                command_key=arguments.idempotency_key,
                release_path=arguments.release,
            )
        except (CatalogVectorSpaceActivationConflict, PermissionError) as error:
            parser.error(str(error))
        print(approval.id)
    return 0


def _normalize_email(email: str) -> str:
    value = email.strip().lower()
    if not value:
        raise ValueError("actor email must not be empty")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
