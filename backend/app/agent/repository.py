"""Flush-only SQLAlchemy adapter for the Agent ledger repository port."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent.models import AgentEvent, AgentInvocation, AgentLease, AgentRun, AgentThread


class SqlAlchemyAgentRepository:
    """Persistence adapter only; service code owns transactions and policy decisions."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add_thread(self, thread: AgentThread) -> AgentThread:
        self._session.add(thread)
        self._session.flush()
        return thread

    def get_thread_for_user(
        self, *, thread_id: uuid.UUID, user_id: uuid.UUID, for_update: bool = False
    ) -> AgentThread | None:
        statement = select(AgentThread).where(
            AgentThread.id == thread_id, AgentThread.user_id == user_id
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def add_run(self, run: AgentRun) -> AgentRun:
        self._session.add(run)
        self._session.flush()
        return run

    def get_run_for_command_for_user(
        self, *, thread_id: uuid.UUID, user_id: uuid.UUID, command_key: str, for_update: bool = False
    ) -> AgentRun | None:
        statement = select(AgentRun).where(
            AgentRun.thread_id == thread_id,
            AgentRun.user_id == user_id,
            AgentRun.command_key == command_key,
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def get_run_for_user(
        self, *, run_id: uuid.UUID, user_id: uuid.UUID, for_update: bool = False
    ) -> AgentRun | None:
        statement = select(AgentRun).where(AgentRun.id == run_id, AgentRun.user_id == user_id)
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def next_event_seq_for_thread_for_user(
        self, *, thread_id: uuid.UUID, user_id: uuid.UUID
    ) -> int:
        # Locking the owning thread serializes sequence allocation without a read-then-
        # compare race on events.  A mismatched tenant never reaches event metadata.
        thread = self.get_thread_for_user(thread_id=thread_id, user_id=user_id, for_update=True)
        if thread is None:
            raise LookupError("agent thread is unavailable")
        return int(
            self._session.scalar(
                select(func.coalesce(func.max(AgentEvent.seq), 0)).where(
                    AgentEvent.thread_id == thread_id,
                    AgentEvent.user_id == user_id,
                )
            )
            or 0
        ) + 1

    def add_event(self, event: AgentEvent) -> AgentEvent:
        self._session.add(event)
        self._session.flush()
        return event

    def list_events_for_thread_for_user(
        self, *, thread_id: uuid.UUID, user_id: uuid.UUID, after_seq: int = 0
    ) -> list[AgentEvent]:
        return list(
            self._session.scalars(
                select(AgentEvent)
                .where(
                    AgentEvent.thread_id == thread_id,
                    AgentEvent.user_id == user_id,
                    AgentEvent.seq > after_seq,
                )
                .order_by(AgentEvent.seq)
            )
        )

    def get_latest_run_for_thread_for_user(
        self, *, thread_id: uuid.UUID, user_id: uuid.UUID
    ) -> AgentRun | None:
        return self._session.scalar(
            select(AgentRun)
            .where(AgentRun.thread_id == thread_id, AgentRun.user_id == user_id)
            .order_by(AgentRun.created_at.desc())
        )

    def get_invocation_for_user_for_update(
        self,
        *,
        run_id: uuid.UUID,
        user_id: uuid.UUID,
        node_name: str,
        item_key: str,
        input_version: str,
        operation_version: str,
        request_hash: str,
    ) -> AgentInvocation | None:
        return self._session.scalar(
            select(AgentInvocation)
            .where(
                AgentInvocation.run_id == run_id,
                AgentInvocation.user_id == user_id,
                AgentInvocation.node_name == node_name,
                AgentInvocation.item_key == item_key,
                AgentInvocation.input_version == input_version,
                AgentInvocation.operation_version == operation_version,
                AgentInvocation.request_hash == request_hash,
            )
            .with_for_update()
        )

    def add_invocation(self, invocation: AgentInvocation) -> AgentInvocation:
        self._session.add(invocation)
        self._session.flush()
        return invocation

    def get_lease_for_run_for_update(
        self, *, run_id: uuid.UUID, user_id: uuid.UUID
    ) -> AgentLease | None:
        # Ownership travels through the run join, never from a caller-provided run UUID.
        return self._session.scalar(
            select(AgentLease)
            .join(AgentRun, AgentLease.run_id == AgentRun.id)
            .where(AgentLease.run_id == run_id, AgentRun.user_id == user_id)
            .with_for_update()
        )

    def add_lease(self, lease: AgentLease) -> AgentLease:
        self._session.add(lease)
        self._session.flush()
        return lease
