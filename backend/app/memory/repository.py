"""Flush-only local authorization ledger adapter for memory operations."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.records.models import (
    MemoryDeletionOutbox,
    MemoryProvisionOutbox,
    PreferenceMemoryLedger,
)


class SqlAlchemyMemoryLedgerRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_ledger(self, ledger: PreferenceMemoryLedger) -> PreferenceMemoryLedger:
        self._session.add(ledger)
        self._session.flush()
        return ledger

    def get_active_for_user(self, *, ledger_id: uuid.UUID, user_id: uuid.UUID, for_update: bool = False) -> PreferenceMemoryLedger | None:
        statement = select(PreferenceMemoryLedger).where(PreferenceMemoryLedger.id == ledger_id, PreferenceMemoryLedger.user_id == user_id, PreferenceMemoryLedger.is_active.is_(True), PreferenceMemoryLedger.deleted_at.is_(None))
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def get_for_user(self, *, ledger_id: uuid.UUID, user_id: uuid.UUID) -> PreferenceMemoryLedger | None:
        return self._session.scalar(select(PreferenceMemoryLedger).where(PreferenceMemoryLedger.id == ledger_id, PreferenceMemoryLedger.user_id == user_id))

    def list_active_for_user(self, *, user_id: uuid.UUID) -> list[PreferenceMemoryLedger]:
        return list(self._session.scalars(select(PreferenceMemoryLedger).where(PreferenceMemoryLedger.user_id == user_id, PreferenceMemoryLedger.is_active.is_(True), PreferenceMemoryLedger.deleted_at.is_(None)).order_by(PreferenceMemoryLedger.category, PreferenceMemoryLedger.updated_at.desc(), PreferenceMemoryLedger.id.desc())))

    def add_outbox(self, outbox: MemoryDeletionOutbox) -> MemoryDeletionOutbox:
        self._session.add(outbox)
        self._session.flush()
        return outbox

    def list_due_outbox(self, *, due_at: datetime) -> list[MemoryDeletionOutbox]:
        return list(self._session.scalars(select(MemoryDeletionOutbox).where(MemoryDeletionOutbox.status == "pending", MemoryDeletionOutbox.not_before <= due_at, MemoryDeletionOutbox.deleted_at.is_(None)).order_by(MemoryDeletionOutbox.not_before, MemoryDeletionOutbox.id).with_for_update(skip_locked=True)))

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
    ) -> PreferenceMemoryLedger:
        existing = self._session.scalar(
            select(PreferenceMemoryLedger)
            .where(
                PreferenceMemoryLedger.user_id == user_id,
                PreferenceMemoryLedger.source_run_id == source_run_id,
                PreferenceMemoryLedger.category == category,
                PreferenceMemoryLedger.request_key_digest == request_key_digest,
            )
            .with_for_update()
        )
        if existing is not None:
            return existing
        active = self._session.scalar(
            select(PreferenceMemoryLedger)
            .where(
                PreferenceMemoryLedger.user_id == user_id,
                PreferenceMemoryLedger.category == category,
                PreferenceMemoryLedger.canonical_text == canonical_text,
                PreferenceMemoryLedger.is_active.is_(True),
                PreferenceMemoryLedger.deleted_at.is_(None),
            )
            .with_for_update()
        )
        if active is not None:
            return active
        try:
            with self._session.begin_nested():
                ledger = PreferenceMemoryLedger(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    source_run_id=source_run_id,
                    category=category,
                    source_kind="user_statement",
                    canonical_text=canonical_text,
                    request_key_digest=request_key_digest,
                    provisioning_status="pending",
                    external_memory_id=None,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                    deleted_at=None,
                )
                self._session.add(ledger)
                self._session.flush()
                self._session.add(
                    MemoryProvisionOutbox(
                        id=uuid.uuid4(),
                        user_id=user_id,
                        ledger_id=ledger.id,
                        operation="provision_external_memory",
                        request_key=request_key,
                        attempt=0,
                        not_before=now,
                        status="pending",
                        claimed_at=None,
                        completed_at=None,
                        created_at=now,
                        updated_at=now,
                        deleted_at=None,
                    )
                )
                self._session.flush()
                return ledger
        except IntegrityError:
            existing = self._session.scalar(
                select(PreferenceMemoryLedger)
                .where(
                    PreferenceMemoryLedger.user_id == user_id,
                    PreferenceMemoryLedger.category == category,
                    PreferenceMemoryLedger.canonical_text == canonical_text,
                    PreferenceMemoryLedger.is_active.is_(True),
                    PreferenceMemoryLedger.deleted_at.is_(None),
                )
                .with_for_update()
            )
            if existing is not None:
                return existing
            raise

    def cancel_pending_provision(
        self, *, ledger_id: uuid.UUID, user_id: uuid.UUID, now: datetime
    ) -> bool:
        intent = self._session.scalar(
            select(MemoryProvisionOutbox)
            .where(
                MemoryProvisionOutbox.ledger_id == ledger_id,
                MemoryProvisionOutbox.user_id == user_id,
                MemoryProvisionOutbox.status == "pending",
                MemoryProvisionOutbox.deleted_at.is_(None),
            )
            .with_for_update()
        )
        if intent is None:
            return False
        intent.status = "cancelled"
        intent.updated_at = now
        return True

    def get_provision_for_ledger(
        self, *, ledger_id: uuid.UUID, user_id: uuid.UUID
    ) -> MemoryProvisionOutbox | None:
        return self._session.scalar(
            select(MemoryProvisionOutbox).where(
                MemoryProvisionOutbox.ledger_id == ledger_id,
                MemoryProvisionOutbox.user_id == user_id,
                MemoryProvisionOutbox.deleted_at.is_(None),
            )
        )

    def list_due_provisioning(self, *, due_at: datetime) -> list[MemoryProvisionOutbox]:
        return list(
            self._session.scalars(
                select(MemoryProvisionOutbox)
                .where(
                    MemoryProvisionOutbox.status.in_(("pending", "outcome_unknown")),
                    MemoryProvisionOutbox.not_before <= due_at,
                    MemoryProvisionOutbox.deleted_at.is_(None),
                )
                .order_by(MemoryProvisionOutbox.not_before, MemoryProvisionOutbox.id)
                .with_for_update(skip_locked=True)
            )
        )

    def claim_due_provisioning(
        self, *, due_at: datetime, now: datetime
    ) -> tuple[MemoryProvisionOutbox, str] | None:
        """Claim one intent after locking its ledger first, matching delete's lock order."""
        candidate = self._session.execute(
            select(PreferenceMemoryLedger, MemoryProvisionOutbox)
            .join(MemoryProvisionOutbox, MemoryProvisionOutbox.ledger_id == PreferenceMemoryLedger.id)
            .where(
                MemoryProvisionOutbox.status.in_(("pending", "outcome_unknown")),
                MemoryProvisionOutbox.not_before <= due_at,
                MemoryProvisionOutbox.deleted_at.is_(None),
            )
            .order_by(MemoryProvisionOutbox.not_before, MemoryProvisionOutbox.id)
            .with_for_update(of=PreferenceMemoryLedger, skip_locked=True)
            .limit(1)
        ).first()
        if candidate is None:
            return None
        ledger, intent = candidate
        intent = self._session.scalar(
            select(MemoryProvisionOutbox)
            .where(MemoryProvisionOutbox.id == intent.id)
            .with_for_update()
        )
        if intent is None or intent.status not in {"pending", "outcome_unknown"}:
            return None
        previous_status = intent.status
        if ledger.deleted_at is not None or not ledger.is_active:
            intent.status = "cancelled"
            intent.updated_at = now
            ledger.provisioning_status = "cancelled"
            ledger.updated_at = now
            return None
        intent.status = "claimed"
        intent.claimed_at = now
        intent.updated_at = now
        ledger.provisioning_status = "claimed"
        ledger.updated_at = now
        self._session.flush()
        return intent, previous_status

    def recheck_claimed_provision(
        self, *, provision_id: uuid.UUID, user_id: uuid.UUID, now: datetime
    ) -> tuple[PreferenceMemoryLedger, MemoryProvisionOutbox] | None:
        """Reacquire locks immediately before network I/O; deleted always wins."""
        locked = self._locked_provision_and_ledger(provision_id=provision_id, user_id=user_id)
        if locked is None:
            return None
        ledger, intent = locked
        if ledger is None or intent.status != "claimed" or ledger.deleted_at is not None or not ledger.is_active:
            intent.status = "cancelled"
            intent.updated_at = now
            if ledger is not None:
                ledger.provisioning_status = "cancelled"
                ledger.updated_at = now
            return None
        return ledger, intent

    def bind_provision_or_schedule_deletion(
        self,
        *,
        provision_id: uuid.UUID,
        user_id: uuid.UUID,
        external_id: str,
        now: datetime,
    ) -> bool:
        """Bind only an active ledger; otherwise preserve a durable remote-delete intent."""
        locked = self._locked_provision_and_ledger(provision_id=provision_id, user_id=user_id)
        if locked is None:
            return False
        ledger, intent = locked
        intent.status = "provisioned"
        intent.completed_at = now
        intent.updated_at = now
        if ledger.deleted_at is not None or not ledger.is_active:
            self.ensure_deletion_intent(
                ledger_id=ledger.id,
                user_id=user_id,
                request_key=intent.request_key,
                now=now,
            )
            self._session.flush()
            return False
        ledger.external_memory_id = external_id
        ledger.provisioning_status = "provisioned"
        ledger.updated_at = now
        self._session.flush()
        return True

    def record_provision_unknown(
        self,
        *,
        provision_id: uuid.UUID,
        user_id: uuid.UUID,
        now: datetime,
        retry_max_attempts: int,
        retry_backoff_seconds: int,
    ) -> None:
        locked = self._locked_provision_and_ledger(provision_id=provision_id, user_id=user_id)
        if locked is None:
            return
        ledger, intent = locked
        if ledger is None or ledger.deleted_at is not None or not ledger.is_active:
            intent.status = "cancelled"
            intent.updated_at = now
            if ledger is not None:
                ledger.provisioning_status = "cancelled"
                ledger.updated_at = now
            return
        intent.attempt += 1
        intent.status = "failed" if intent.attempt >= retry_max_attempts else "outcome_unknown"
        intent.not_before = now + timedelta(
            seconds=retry_backoff_seconds * (2 ** (intent.attempt - 1))
        )
        intent.updated_at = now
        ledger.provisioning_status = intent.status
        ledger.updated_at = now
        self._session.flush()

    def ensure_deletion_intent(
        self,
        *,
        ledger_id: uuid.UUID,
        user_id: uuid.UUID,
        request_key: str | None,
        now: datetime,
    ) -> MemoryDeletionOutbox:
        """Re-open an early no-op delete if remote create finishes after it was checked."""
        outbox = self._session.scalar(
            select(MemoryDeletionOutbox)
            .where(
                MemoryDeletionOutbox.ledger_id == ledger_id,
                MemoryDeletionOutbox.operation == "delete_external_memory",
            )
            .with_for_update()
        )
        if outbox is not None:
            outbox.request_key = request_key or outbox.request_key
            outbox.status = "pending"
            outbox.attempt = 0
            outbox.not_before = now
            outbox.updated_at = now
            self._session.flush()
            return outbox
        outbox = MemoryDeletionOutbox(
            id=uuid.uuid4(),
            user_id=user_id,
            ledger_id=ledger_id,
            operation="delete_external_memory",
            request_key=request_key,
            attempt=0,
            not_before=now,
            status="pending",
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
        self._session.add(outbox)
        self._session.flush()
        return outbox

    def _locked_provision_and_ledger(
        self, *, provision_id: uuid.UUID, user_id: uuid.UUID
    ) -> tuple[PreferenceMemoryLedger, MemoryProvisionOutbox] | None:
        """Always lock ledger then provision intent so delete/provision cannot deadlock."""
        candidate = self._session.scalar(
            select(MemoryProvisionOutbox).where(
                MemoryProvisionOutbox.id == provision_id,
                MemoryProvisionOutbox.user_id == user_id,
            )
        )
        if candidate is None:
            return None
        ledger = self._session.scalar(
            select(PreferenceMemoryLedger)
            .where(PreferenceMemoryLedger.id == candidate.ledger_id, PreferenceMemoryLedger.user_id == user_id)
            .with_for_update()
        )
        if ledger is None:
            return None
        intent = self._session.scalar(
            select(MemoryProvisionOutbox)
            .where(MemoryProvisionOutbox.id == provision_id, MemoryProvisionOutbox.user_id == user_id)
            .with_for_update()
        )
        return (ledger, intent) if intent is not None else None
