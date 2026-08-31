"""Flush-only local authorization ledger adapter for memory operations."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.records.models import MemoryDeletionOutbox, PreferenceMemoryLedger


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
