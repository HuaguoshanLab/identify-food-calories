"""Preview or enqueue one user's legacy Fake replicas for durable Mem0 provisioning."""

from __future__ import annotations

import argparse
import uuid

from sqlalchemy.engine import make_url

# Register the ledger's foreign-key targets in a standalone process.
from app.agent import models as agent_models  # noqa: F401
from app.admin import models as admin_models  # noqa: F401
from app.core.config import Settings, runtime_database_url
from app.core.database import create_session_factory
from app.memory.providers import create_memory_provider
from app.memory.repository import SqlAlchemyMemoryLedgerRepository
from app.memory.service import MemoryService


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", type=uuid.UUID, required=True)
    parser.add_argument("--apply", action="store_true", help="Queue the previewed Fake replicas")
    args = parser.parse_args()
    settings = Settings()
    if settings.app_env != "local" or settings.memory_provider_mode != "mem0":
        parser.error("requires APP_ENV=local and MEMORY_PROVIDER_MODE=mem0")
    database = make_url(runtime_database_url(settings))
    if database.host not in {"localhost", "127.0.0.1", "::1"} or database.database != "food_agent_dev":
        parser.error("requires the loopback food_agent_dev database")
    with create_session_factory(settings)() as session:
        repository = SqlAlchemyMemoryLedgerRepository(session)
        candidates = [item for item in repository.list_active_for_user(user_id=args.user_id)
                      if (item.external_memory_id or "").startswith(("fake-memory-", "fake-direct-"))]
        print(f"Legacy Fake replicas: {len(candidates)}")
        if not args.apply:
            print("Preview only; use --apply to enqueue migration.")
            return
        # Verify cloud credentials before changing any local replica binding.
        service = MemoryService(repository=repository, provider=create_memory_provider(settings),
                                commit=session.commit, rollback=session.rollback)
        queued = sum(service.queue_fake_replica_migration(memory_id=item.id, user_id=args.user_id)
                     for item in candidates)
        print(f"Queued: {queued}; skipped: {len(candidates) - queued}. The running lifecycle worker performs cloud I/O.")


if __name__ == "__main__":
    main()
