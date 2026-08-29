"""Narrow persistence interfaces consumed by Agent application services."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from app.agent.models import (
    AgentDeletionIntent,
    AgentEvent,
    AgentInvocation,
    AgentLease,
    AgentRun,
    AgentThread,
)


class AgentRepository(Protocol):
    """Every user-facing lookup takes user_id so ownership is proved in SQL."""

    def add_thread(self, thread: AgentThread) -> AgentThread: ...

    def get_thread_for_user(
        self, *, thread_id: uuid.UUID, user_id: uuid.UUID, for_update: bool = False
    ) -> AgentThread | None: ...

    def add_run(self, run: AgentRun) -> AgentRun: ...

    def get_run_for_command_for_user(
        self, *, thread_id: uuid.UUID, user_id: uuid.UUID, command_key: str, for_update: bool = False
    ) -> AgentRun | None: ...

    def get_run_for_user(
        self, *, run_id: uuid.UUID, user_id: uuid.UUID, for_update: bool = False
    ) -> AgentRun | None: ...

    def next_event_seq_for_thread_for_user(
        self, *, thread_id: uuid.UUID, user_id: uuid.UUID
    ) -> int: ...

    def add_event(self, event: AgentEvent) -> AgentEvent: ...

    def list_events_for_thread_for_user(
        self, *, thread_id: uuid.UUID, user_id: uuid.UUID, after_seq: int = 0
    ) -> list[AgentEvent]: ...

    def get_latest_run_for_thread_for_user(
        self, *, thread_id: uuid.UUID, user_id: uuid.UUID
    ) -> AgentRun | None: ...

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
    ) -> AgentInvocation | None: ...

    def add_invocation(self, invocation: AgentInvocation) -> AgentInvocation: ...

    def get_lease_for_run_for_update(
        self, *, run_id: uuid.UUID, user_id: uuid.UUID
    ) -> AgentLease | None: ...

    def add_lease(self, lease: AgentLease) -> AgentLease: ...

    def add_deletion_intent(self, intent: AgentDeletionIntent) -> AgentDeletionIntent: ...

    def get_deletion_intent_for_thread_for_user(
        self, *, thread_id: uuid.UUID, user_id: uuid.UUID, for_update: bool = False
    ) -> AgentDeletionIntent | None: ...

    def list_due_deletion_intents(self, *, due_at: datetime) -> list[AgentDeletionIntent]: ...

    def list_threads_inactive_before(self, *, cutoff: datetime) -> list[AgentThread]: ...

    def delete_events_for_thread_for_user(
        self, *, thread_id: uuid.UUID, user_id: uuid.UUID
    ) -> int: ...

    def list_runs_updated_before(self, *, cutoff: datetime) -> list[AgentRun]: ...

    def delete_run_for_user(self, *, run_id: uuid.UUID, user_id: uuid.UUID) -> bool: ...

    def delete_thread_for_user(self, *, thread_id: uuid.UUID, user_id: uuid.UUID) -> bool: ...

    def earliest_pending_deletion_at(self) -> datetime | None: ...

    def earliest_thread_activity_at(self) -> datetime | None: ...

    def earliest_run_updated_at(self) -> datetime | None: ...
