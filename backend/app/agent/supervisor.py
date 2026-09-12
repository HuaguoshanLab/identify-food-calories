"""PostgreSQL-backed lease supervisor for durable Agent execution ownership."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agent.models import AgentLease
from app.agent.repository import SqlAlchemyAgentRepository
from app.agent.retention import RetentionWorker
from app.agent.service import AgentService, RetentionPolicy
from app.core.tracing import DisabledTracingRuntime, TracingRuntime
from app.images.service import ImageSafetyService


logger = logging.getLogger(__name__)


class EmbeddingWorker(Protocol):
    """Small synchronous seam so the supervisor can own a single worker task."""

    def run_once(self) -> str: ...


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
        self._embedding_worker_task: asyncio.Task[None] | None = None
        self._embedding_worker_stop = asyncio.Event()

    @property
    def started(self) -> bool:
        return self._started

    @property
    def retention_worker(self) -> RetentionWorker | None:
        return self._retention_worker

    @property
    def embedding_worker_started(self) -> bool:
        """Expose lifecycle state without leaking job payloads or provider details."""

        return self._embedding_worker_task is not None and not self._embedding_worker_task.done()

    async def start(self) -> None:
        """Mark the lifecycle participant ready; setup remains an explicit CLI step."""

        self._started = True

    async def stop(self) -> None:
        try:
            if self._embedding_worker_task is not None:
                self._embedding_worker_stop.set()
                await self._embedding_worker_task
                self._embedding_worker_task = None
            if self._retention_worker is not None:
                await self._retention_worker.stop()
                self._retention_worker = None
        finally:
            self._started = False

    async def start_embedding_worker(
        self, *, worker: EmbeddingWorker, poll_interval: timedelta
    ) -> None:
        """Start one bounded background owner after supervisor readiness.

        PostgreSQL leases still coordinate actual jobs across processes; this task only
        owns the process-local scheduling loop and therefore never creates work itself.
        """

        if not self._started:
            raise RuntimeError("lease supervisor has not started")
        if poll_interval <= timedelta(0) or poll_interval > timedelta(minutes=5):
            raise ValueError("embedding worker poll interval must be within (0, 5 minutes]")
        if self._embedding_worker_task is None:
            self._embedding_worker_stop.clear()
            self._embedding_worker_task = asyncio.create_task(
                self._run_embedding_worker(worker=worker, poll_interval=poll_interval),
                name="catalog-embedding-worker",
            )

    async def _run_embedding_worker(
        self, *, worker: EmbeddingWorker, poll_interval: timedelta
    ) -> None:
        while not self._embedding_worker_stop.is_set():
            try:
                await asyncio.to_thread(worker.run_once)
            except Exception:
                # Job-level failures are persisted by the worker. A broken provider or
                # database connection must not take down HTTP fallback retrieval. Log
                # no job payload, but retain the traceback needed to diagnose a worker
                # that would otherwise silently leave durable jobs pending forever.
                logger.exception("catalog embedding worker pass failed")
            try:
                await asyncio.wait_for(
                    self._embedding_worker_stop.wait(), timeout=poll_interval.total_seconds()
                )
            except TimeoutError:
                pass

    async def start_retention(
        self,
        *,
        checkpointer: object,
        policy: RetentionPolicy,
        image_safety: ImageSafetyService,
        memory_provider_work: Callable[[], tuple[int, int]] | None = None,
        memory_cleanup: Callable[[], tuple[int, int]] | None = None,
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
                memory_provider_work=memory_provider_work,
                memory_cleanup=memory_cleanup,
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
            # A competing run must not exhaust a worker indefinitely.
            session.execute(text("SET LOCAL lock_timeout = '5s'"))
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
