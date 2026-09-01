"""Flush-only local authorization ledger adapter for memory operations."""

from __future__ import annotations

import uuid
from datetime import datetime

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
