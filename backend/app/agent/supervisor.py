"""PostgreSQL-backed lease supervisor for durable Agent execution ownership."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.agent.models import AgentLease
from app.agent.repository import SqlAlchemyAgentRepository
from app.agent.retention import RetentionWorker
from app.agent.service import AgentService, RetentionPolicy
from app.core.tracing import DisabledTracingRuntime, TracingRuntime
from app.images.service import ImageSafetyService


class PostgresLeaseSupervisor:
    """Claims durable per-run leases; it intentionally owns no process-local lock."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        holder_id: str,
        lease_duration: timedelta = timedelta(seconds=30),
        now: Callable[[], datetime] | None = None,
        tracing: TracingRuntime | None = None,
    ) -> None:
        if not holder_id.strip():
            raise ValueError("lease holder_id is required")
        if lease_duration <= timedelta(0):
            raise ValueError("lease_duration must be positive")
        self._session_factory = session_factory
        self._holder_id = holder_id
        self._lease_duration = lease_duration
        self._now = now or (lambda: datetime.now(UTC))
        self._tracing = tracing or DisabledTracingRuntime()
        self._started = False
        self._retention_worker: RetentionWorker | None = None

    @property
    def started(self) -> bool:
        return self._started

    @property
    def retention_worker(self) -> RetentionWorker | None:
        return self._retention_worker

    async def start(self) -> None:
        """Mark the lifecycle participant ready; setup remains an explicit CLI step."""

        self._started = True

    async def stop(self) -> None:
        try:
            if self._retention_worker is not None:
                await self._retention_worker.stop()
                self._retention_worker = None
            self._tracing.flush()
        finally:
            self._tracing.shutdown()
            self._started = False

    async def start_retention(
        self,
        *,
        checkpointer: object,
        policy: RetentionPolicy,
        image_safety: ImageSafetyService,
        now: Callable[[], datetime] | None = None,
    ) -> RetentionWorker:
        """Attach the D-18 scheduler to the same real lifespan as Agent execution."""

        if not self._started:
            raise RuntimeError("lease supervisor has not started")
        if self._retention_worker is None:
            self._retention_worker = RetentionWorker(
                session_factory=self._session_factory,
                checkpointer=checkpointer,
                policy=policy,
                image_safety=image_safety,
                now=now,
            )
            await self._retention_worker.start()
        return self._retention_worker

    @contextmanager
    def run_span(
        self,
        *,
        thread_id: uuid.UUID,
        graph_version: str,
        prompt_version: str,
        tool_version: str,
    ) -> Iterator[None]:
        """Scope a single graph run without exporting identity or submitted meal content."""

        if not self._started:
            raise RuntimeError("lease supervisor has not started")
        with self._tracing.span(
            "agent.run",
            {
                "node.name": "meal_analysis",
                "graph.version": graph_version,
                "prompt.version": prompt_version,
                "tool.version": tool_version,
                "thread.fingerprint": self._tracing.scoped_hmac(str(thread_id)),
            },
        ):
            yield

    def claim(self, *, run_id: uuid.UUID, user_id: uuid.UUID) -> AgentLease:
        if not self._started:
            raise RuntimeError("lease supervisor has not started")
        with self._session_factory() as session:
            service = AgentService(
                repository=SqlAlchemyAgentRepository(session),
                now=self._now,
                commit=session.commit,
                rollback=session.rollback,
            )
            return service.claim_lease(
                run_id=run_id,
                user_id=user_id,
                holder_id=self._holder_id,
                duration=self._lease_duration,
            )
