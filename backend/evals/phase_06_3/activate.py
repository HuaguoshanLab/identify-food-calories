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
    parser.add_argument("--actor-user-id", type=uuid.UUID, required=True)
    parser.add_argument("--vector-space-id", type=uuid.UUID, required=True)
    parser.add_argument("--build-id", type=uuid.UUID, required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--idempotency-key", required=True)
    parser.add_argument("--release", type=Path, default=Path(__file__).with_name("release.json"))
    arguments = parser.parse_args(sys.argv[1:] if argv is None else argv)
    session_factory = create_session_factory()
    with session_factory() as session:
        service = AdminService(
            repository=SqlAlchemyAdminRepository(session),
            commit=session.commit,
            rollback=session.rollback,
        )
        try:
            approval = service.activate_vector_space(
                actor_user_id=arguments.actor_user_id,
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


if __name__ == "__main__":
    raise SystemExit(main())
