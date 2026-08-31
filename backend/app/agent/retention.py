"""Durable D-18 cleanup scheduler owned by the FastAPI lifespan.

The worker holds a PostgreSQL advisory lock for one sweep.  This is deliberately a
database lease rather than an asyncio mutex: another process cannot delete the same
tenant's data, and a crashed process releases its connection-bound lease automatically.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agent.repository import SqlAlchemyAgentRepository
from app.agent.service import AgentService, RetentionPolicy, RetentionSweep
from app.images.service import ImageSafetyService


_RETENTION_ADVISORY_LOCK_KEY = 2_140_022_014


@dataclass(frozen=True, slots=True)
class RetentionRunStats:
    """Safe operational counters; never include thread IDs, users or meal content."""

    deleted_threads: int = 0
    cleared_checkpoint_namespaces: int = 0
    deleted_events: int = 0
    deleted_runs: int = 0
    deleted_images: int = 0
    deleted_memories: int = 0
    failed_memory_deletions: int = 0


class RetentionWorker:
    """Run explicit retention sweeps and sleep until the first eligibility boundary."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        checkpointer: object,
        policy: RetentionPolicy,
        image_safety: ImageSafetyService,
        memory_cleanup: Callable[[], tuple[int, int]] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if policy.poll_interval <= timedelta(0) or policy.poll_interval > timedelta(minutes=5):
            raise ValueError("retention poll interval must be within (0, 5 minutes]")
        if policy.deletion_due_delta <= timedelta(0):
            raise ValueError("retention deletion due interval must be positive")
        self._session_factory = session_factory
        self._checkpointer = checkpointer
        self._policy = policy
        self._image_safety = image_safety
        self._memory_cleanup = memory_cleanup
        self._now = now or (lambda: datetime.now(UTC))
        self._task: asyncio.Task[None] | None = None
        self._stopping = False
        self._wake = asyncio.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._last_stats = RetentionRunStats()
        self._completed_sweeps = 0
        self._sweep_completed = asyncio.Condition()

    @property
    def started(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def last_stats(self) -> RetentionRunStats:
        return self._last_stats

    @property
    def completed_sweeps(self) -> int:
        return self._completed_sweeps

    def wake(self) -> None:
        """Wake this process after a persisted deletion intent; the database remains authority."""

        if self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._wake.set)
            return
        self._wake.set()

    async def start(self) -> None:
        if self._task is None:
            self._stopping = False
            self._loop = asyncio.get_running_loop()
            self._task = asyncio.create_task(self._run(), name="agent-retention-worker")

    async def stop(self) -> None:
        self._stopping = True
        self._wake.set()
        if self._task is not None:
            await self._task
            self._task = None
        self._loop = None

    async def wait_for_sweep(self, *, after: int) -> int:
        """Observe a scheduler-owned cycle in tests without starting cleanup directly."""

        async with self._sweep_completed:
            await self._sweep_completed.wait_for(lambda: self._completed_sweeps > after)
            return self._completed_sweeps

    async def _run(self) -> None:
        while not self._stopping:
            delay = await self._sweep_and_next_delay()
            self._wake.clear()
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=max(delay.total_seconds(), 0))
            except TimeoutError:
                pass

    async def _sweep_and_next_delay(self) -> timedelta:
        lease_session = self._try_claim_postgres_lease()
        if lease_session is None:
            return self._policy.poll_interval
        try:
            sweep = self._select_sweep()
            stats = await self._apply_sweep(sweep)
            self._last_stats = stats
            async with self._sweep_completed:
                self._completed_sweeps += 1
                self._sweep_completed.notify_all()
            earliest = self._select_sweep().next_eligible_at
            return self._next_delay(earliest)
        finally:
            self._release_postgres_lease(lease_session)

    def _try_claim_postgres_lease(self) -> Session | None:
        session = self._session_factory()
        try:
            claimed = session.scalar(
                text("SELECT pg_try_advisory_lock(:lock_key)"),
                {"lock_key": _RETENTION_ADVISORY_LOCK_KEY},
            )
            if claimed is True:
                return session
        except Exception:
            session.rollback()
            raise
        session.close()
        return None

    @staticmethod
    def _release_postgres_lease(session: Session) -> None:
        try:
            session.execute(
                text("SELECT pg_advisory_unlock(:lock_key)"),
                {"lock_key": _RETENTION_ADVISORY_LOCK_KEY},
            )
        finally:
            session.rollback()
            session.close()

    def _service(self) -> tuple[Session, AgentService]:
        session = self._session_factory()
        return session, AgentService(
            repository=SqlAlchemyAgentRepository(session),
            now=self._now,
            commit=session.commit,
            rollback=session.rollback,
        )

    def _select_sweep(self) -> RetentionSweep:
        session, service = self._service()
        try:
            return service.retention_sweep(policy=self._policy)
        finally:
            session.close()

    async def _apply_sweep(self, sweep: RetentionSweep) -> RetentionRunStats:
        deleted_threads = 0
        checkpoint_namespaces = 0
        deleted_events = 0
        deleted_runs = 0
        deleted_images = 0
        deleted_memories = 0
        failed_memory_deletions = 0
        deletion_threads = {thread_id for thread_id, _user_id in sweep.due_deletions}

        for thread_id, user_id in sweep.due_deletions:
            image_count, images_removed = self._delete_thread_images(
                thread_id=thread_id, user_id=user_id
            )
            deleted_images += image_count
            if not images_removed:
                # Do not cascade away the only durable retry record when private-file deletion
                # failed. A later sweep will select the same delete_failed image again.
                continue
            await self._delete_checkpoint_thread(thread_id)
            checkpoint_namespaces += 1
            session, service = self._service()
            try:
                deleted_threads += int(
                    service.finalize_thread_deletion(thread_id=thread_id, user_id=user_id)
                )
            finally:
                session.close()

        for thread_id, user_id in sweep.inactive_threads:
            if thread_id in deletion_threads:
                continue
            await self._delete_checkpoint_thread(thread_id)
            checkpoint_namespaces += 1
            session, service = self._service()
            try:
                deleted_events += service.purge_expired_thread_events(
                    thread_id=thread_id, user_id=user_id
                )
            finally:
                session.close()

        for run_id, user_id in sweep.expired_runs:
            session, service = self._service()
            try:
                deleted_runs += int(service.purge_expired_run(run_id=run_id, user_id=user_id))
            finally:
                session.close()
        for image_id, user_id in sweep.expired_images:
            deleted_images += self._delete_image(image_id=image_id, user_id=user_id)
        if self._memory_cleanup is not None:
            deleted_memories, failed_memory_deletions = self._memory_cleanup()
        return RetentionRunStats(
            deleted_threads=deleted_threads,
            cleared_checkpoint_namespaces=checkpoint_namespaces,
            deleted_events=deleted_events,
            deleted_runs=deleted_runs,
            deleted_images=deleted_images,
            deleted_memories=deleted_memories,
            failed_memory_deletions=failed_memory_deletions,
        )

    def _delete_thread_images(
        self, *, thread_id: uuid.UUID, user_id: uuid.UUID
    ) -> tuple[int, bool]:
        session, service = self._service()
        try:
            references = service.images_for_thread_cleanup(thread_id=thread_id, user_id=user_id)
            deleted = 0
            for image, reference in references:
                try:
                    self._image_safety.delete(reference)
                except (OSError, ValueError):
                    service.mark_image_deletion_failed(image_id=image.id, user_id=user_id)
                    return deleted, False
                service.mark_image_deleted(image_id=image.id, user_id=user_id)
                deleted += 1
            return deleted, True
        finally:
            session.close()

    def _delete_image(self, *, image_id: uuid.UUID, user_id: uuid.UUID) -> int:
        session, service = self._service()
        try:
            candidate = service.image_for_cleanup(image_id=image_id, user_id=user_id)
            if candidate is None:
                return 0
            image, reference = candidate
            try:
                self._image_safety.delete(reference)
            except (OSError, ValueError):
                service.mark_image_deletion_failed(image_id=image.id, user_id=user_id)
                return 0
            service.mark_image_deleted(image_id=image.id, user_id=user_id)
            return 1
        finally:
            session.close()

    async def _delete_checkpoint_thread(self, thread_id: object) -> None:
        delete_thread = getattr(self._checkpointer, "adelete_thread", None)
        if delete_thread is None:
            raise RuntimeError("configured checkpointer does not support adelete_thread")
        await delete_thread(str(thread_id))

    def _next_delay(self, earliest_eligible_at: datetime | None) -> timedelta:
        now = self._now()
        maximum = now + self._policy.poll_interval
        target = min(maximum, earliest_eligible_at) if earliest_eligible_at is not None else maximum
        return max(target - now, timedelta(0))
