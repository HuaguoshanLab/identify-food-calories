"""PostgreSQL-backed lease supervisor for durable Agent execution ownership."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import timedelta

from sqlalchemy.orm import Session

from app.agent.models import AgentLease
from app.agent.repository import SqlAlchemyAgentRepository
from app.agent.service import AgentService


class PostgresLeaseSupervisor:
    """Claims durable per-run leases; it intentionally owns no process-local lock."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        holder_id: str,
        lease_duration: timedelta = timedelta(seconds=30),
    ) -> None:
        if not holder_id.strip():
            raise ValueError("lease holder_id is required")
        if lease_duration <= timedelta(0):
            raise ValueError("lease_duration must be positive")
        self._session_factory = session_factory
        self._holder_id = holder_id
        self._lease_duration = lease_duration
        self._started = False

    @property
    def started(self) -> bool:
        return self._started

    async def start(self) -> None:
        """Mark the lifecycle participant ready; setup remains an explicit CLI step."""

        self._started = True

    async def stop(self) -> None:
        self._started = False

    def claim(self, *, run_id: uuid.UUID, user_id: uuid.UUID) -> AgentLease:
        if not self._started:
            raise RuntimeError("lease supervisor has not started")
        with self._session_factory() as session:
            service = AgentService(
                repository=SqlAlchemyAgentRepository(session),
                commit=session.commit,
                rollback=session.rollback,
            )
            return service.claim_lease(
                run_id=run_id,
                user_id=user_id,
                holder_id=self._holder_id,
                duration=self._lease_duration,
            )
