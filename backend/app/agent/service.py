"""Application transaction boundary for Agent threads, runs, events and invocations."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.agent.models import AgentEvent, AgentInvocation, AgentLease, AgentRun, AgentThread
from app.agent.ports import AgentRepository


class AgentThreadUnavailable(LookupError):
    """Uniform missing/foreign-thread result; callers must not leak ownership details."""


class AgentCommandConflict(ValueError):
    """A client idempotency key was reused for a different canonical command."""


class AgentLeaseUnavailable(RuntimeError):
    """Another worker currently owns the persisted execution lease."""


GRAPH_VERSION = "meal-agent-graph.v1"
PROMPT_VERSION = "reasoning-parse.v1"
TOOL_VERSION = "nutrition-tools-v1"


def canonical_command_hash(command: dict[str, object]) -> str:
    """Hash canonical JSON; only the digest reaches durable idempotency metadata."""

    payload = json.dumps(command, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class AgentService:
    """Coordinates durable Agent state while keeping graph and ORM concerns separate."""

    def __init__(
        self,
        *,
        repository: AgentRepository,
        now: Callable[[], datetime] | None = None,
        commit: Callable[[], None] | None = None,
        rollback: Callable[[], None] | None = None,
    ) -> None:
        self._repository = repository
        self._now = now or (lambda: datetime.now(UTC))
        self._commit = commit or (lambda: None)
        self._rollback = rollback or (lambda: None)

    def create_thread(self, *, user_id: uuid.UUID) -> AgentThread:
        now = self._now()
        thread = self._repository.add_thread(
            AgentThread(
                id=uuid.uuid4(),
                user_id=user_id,
                status="open",
                revision=0,
                created_at=now,
                last_activity_at=now,
                deleted_at=None,
            )
        )
        self._commit_or_rollback()
        return thread

    def get_thread(self, *, thread_id: uuid.UUID, user_id: uuid.UUID) -> AgentThread:
        thread = self._repository.get_thread_for_user(thread_id=thread_id, user_id=user_id)
        if thread is None or thread.deleted_at is not None:
            raise AgentThreadUnavailable("agent thread is unavailable")
        return thread

    def create_or_reuse_run(
        self,
        *,
        thread_id: uuid.UUID,
        user_id: uuid.UUID,
        command_key: str,
        canonical_command: dict[str, object],
    ) -> AgentRun:
        thread = self._repository.get_thread_for_user(
            thread_id=thread_id, user_id=user_id, for_update=True
        )
        if thread is None or thread.deleted_at is not None:
            raise AgentThreadUnavailable("agent thread is unavailable")
        command_hash = canonical_command_hash(canonical_command)
        existing = self._repository.get_run_for_command_for_user(
            thread_id=thread_id,
            user_id=user_id,
            command_key=command_key,
            for_update=True,
        )
        if existing is not None:
            if existing.command_hash != command_hash:
                raise AgentCommandConflict("idempotency key payload mismatch")
            return existing
        now = self._now()
        run = self._repository.add_run(
            AgentRun(
                id=uuid.uuid4(),
                thread_id=thread_id,
                user_id=user_id,
                command_key=command_key,
                command_hash=command_hash,
                status="accepted",
                graph_version=GRAPH_VERSION,
                prompt_version=PROMPT_VERSION,
                tool_version=TOOL_VERSION,
                model_provider=None,
                model_version=None,
                graph_steps=0,
                model_calls=0,
                tool_calls=0,
                elapsed_ms=0,
                estimated_cost_usd=Decimal("0"),
                failure_code=None,
                created_at=now,
                updated_at=now,
                finished_at=None,
            )
        )
        thread.last_activity_at = now
        thread.revision += 1
        self._commit_or_rollback()
        return run

    def append_safe_event(
        self,
        *,
        thread_id: uuid.UUID,
        user_id: uuid.UUID,
        run_id: uuid.UUID | None,
        event_type: str,
        payload: dict[str, object],
        safe_summary: str,
    ) -> AgentEvent:
        self.get_thread(thread_id=thread_id, user_id=user_id)
        if run_id is not None and self._repository.get_run_for_user(run_id=run_id, user_id=user_id) is None:
            raise AgentThreadUnavailable("agent run is unavailable")
        event = self._repository.add_event(
            AgentEvent(
                id=uuid.uuid4(),
                thread_id=thread_id,
                run_id=run_id,
                user_id=user_id,
                seq=self._repository.next_event_seq_for_thread_for_user(
                    thread_id=thread_id, user_id=user_id
                ),
                event_type=event_type,
                payload=payload,
                safe_summary=safe_summary,
                created_at=self._now(),
            )
        )
        self._commit_or_rollback()
        return event

    def prepare_invocation(
        self,
        *,
        run_id: uuid.UUID,
        user_id: uuid.UUID,
        node_name: str,
        item_key: str,
        input_version: str,
        operation_version: str,
        request_hash: str,
    ) -> AgentInvocation:
        run = self._repository.get_run_for_user(run_id=run_id, user_id=user_id, for_update=True)
        if run is None:
            raise AgentThreadUnavailable("agent run is unavailable")
        existing = self._repository.get_invocation_for_user_for_update(
            run_id=run_id,
            user_id=user_id,
            node_name=node_name,
            item_key=item_key,
            input_version=input_version,
            operation_version=operation_version,
            request_hash=request_hash,
        )
        if existing is not None:
            return existing
        now = self._now()
        invocation = self._repository.add_invocation(
            AgentInvocation(
                id=uuid.uuid4(),
                thread_id=run.thread_id,
                run_id=run.id,
                user_id=user_id,
                node_name=node_name,
                item_key=item_key,
                input_version=input_version,
                operation_version=operation_version,
                request_hash=request_hash,
                status="prepared",
                attempt=0,
                cost_usd=Decimal("0"),
                safe_result_digest=None,
                failure_code=None,
                created_at=now,
                updated_at=now,
            )
        )
        self._commit_or_rollback()
        return invocation

    def claim_lease(
        self,
        *,
        run_id: uuid.UUID,
        user_id: uuid.UUID,
        holder_id: str,
        duration: timedelta,
    ) -> AgentLease:
        if duration <= timedelta(0):
            raise ValueError("lease duration must be positive")
        if self._repository.get_run_for_user(run_id=run_id, user_id=user_id, for_update=True) is None:
            raise AgentThreadUnavailable("agent run is unavailable")
        now = self._now()
        lease = self._repository.get_lease_for_run_for_update(run_id=run_id, user_id=user_id)
        if lease is not None and lease.expires_at > now and lease.holder_id != holder_id:
            raise AgentLeaseUnavailable("agent run is leased")
        if lease is None:
            lease = self._repository.add_lease(
                AgentLease(
                    id=uuid.uuid4(),
                    run_id=run_id,
                    holder_id=holder_id,
                    acquired_at=now,
                    expires_at=now + duration,
                )
            )
        else:
            lease.holder_id = holder_id
            lease.acquired_at = now
            lease.expires_at = now + duration
        self._commit_or_rollback()
        return lease

    def _commit_or_rollback(self) -> None:
        try:
            self._commit()
        except Exception:
            self._rollback()
            raise
