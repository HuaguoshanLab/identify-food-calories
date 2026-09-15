"""Minimal Provider contract: only a canonical preference statement crosses the boundary."""

from __future__ import annotations

import uuid
from datetime import datetime
from dataclasses import dataclass
from typing import Protocol

from app.records.models import (
    MemoryDeletionOutbox,
    MemoryProvisionOutbox,
    PreferenceMemoryLedger,
)


@dataclass(frozen=True, slots=True)
class MemorySearchHit:
    external_id: str
    canonical_text: str


class MemoryReplicaMissing(LookupError):
    """Provider positively confirmed a missing replica, not a timeout or owner mismatch."""


class MemoryProvider(Protocol):
    def create(self, *, user_id: uuid.UUID, category: str, canonical_text: str) -> str: ...
    def resolve_direct_by_request_key(self, *, user_id: uuid.UUID, request_key: str) -> str | None: ...
    def create_direct(self, *, user_id: uuid.UUID, category: str, canonical_text: str, request_key: str) -> str: ...
    def update(self, *, user_id: uuid.UUID, external_id: str, category: str, canonical_text: str) -> None: ...
    def delete(self, *, user_id: uuid.UUID, external_id: str) -> None: ...
    def search(self, *, user_id: uuid.UUID, query: str, limit: int) -> list[MemorySearchHit]: ...


class MemoryLedgerRepository(Protocol):
    def add_ledger(self, ledger: PreferenceMemoryLedger) -> PreferenceMemoryLedger: ...
    def get_active_for_user(self, *, ledger_id: uuid.UUID, user_id: uuid.UUID, for_update: bool = False) -> PreferenceMemoryLedger | None: ...
    def get_for_user(self, *, ledger_id: uuid.UUID, user_id: uuid.UUID) -> PreferenceMemoryLedger | None: ...
    def list_active_for_user(self, *, user_id: uuid.UUID) -> list[PreferenceMemoryLedger]: ...
    def add_outbox(self, outbox: MemoryDeletionOutbox) -> MemoryDeletionOutbox: ...
    def list_due_outbox(self, *, due_at: datetime) -> list[MemoryDeletionOutbox]: ...
    def get_or_create_direct_candidate(
        self,
        *,
        user_id: uuid.UUID,
        source_run_id: uuid.UUID | None,
        category: str,
        canonical_text: str,
        request_key: str,
        request_key_digest: str,
        now: datetime,
    ) -> PreferenceMemoryLedger: ...
    def cancel_pending_provision(
        self, *, ledger_id: uuid.UUID, user_id: uuid.UUID, now: datetime
    ) -> bool: ...
    def get_provision_for_ledger(
        self, *, ledger_id: uuid.UUID, user_id: uuid.UUID
    ) -> MemoryProvisionOutbox | None: ...
    def list_due_provisioning(self, *, due_at: datetime) -> list[MemoryProvisionOutbox]: ...
    def claim_due_provisioning(
        self, *, due_at: datetime, now: datetime
    ) -> tuple[MemoryProvisionOutbox, str] | None: ...
    def recheck_claimed_provision(
        self, *, provision_id: uuid.UUID, user_id: uuid.UUID, now: datetime
    ) -> tuple[PreferenceMemoryLedger, MemoryProvisionOutbox] | None: ...
    def bind_provision_or_schedule_deletion(
        self,
        *,
        provision_id: uuid.UUID,
        user_id: uuid.UUID,
        external_id: str,
        now: datetime,
    ) -> bool: ...
    def record_provision_unknown(
        self,
        *,
        provision_id: uuid.UUID,
        user_id: uuid.UUID,
        now: datetime,
        retry_max_attempts: int,
        retry_backoff_seconds: int,
    ) -> None: ...
    def ensure_deletion_intent(
        self,
        *,
        ledger_id: uuid.UUID,
        user_id: uuid.UUID,
        request_key: str | None,
        now: datetime,
    ) -> MemoryDeletionOutbox: ...
