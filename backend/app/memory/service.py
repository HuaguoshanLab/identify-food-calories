"""Local-ledger authorization, source audit and retryable external-memory deletion."""

from __future__ import annotations

import uuid
from hashlib import sha256
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from app.memory.ports import MemoryLedgerRepository, MemoryProvider
from app.records.models import MemoryDeletionOutbox, PreferenceMemoryLedger


ALLOWED_CATEGORIES = frozenset({"goal", "avoidance", "stable_preference"})


class MemoryUnavailable(LookupError):
    """Uniform missing, foreign or inactive ledger result."""


class MemoryValidationError(ValueError):
    """Only audited preference categories and canonical text are acceptable."""


class MemoryService:
    """Owns local authorization; the provider sees only a minimum canonical statement."""

    def __init__(
        self,
        *,
        repository: MemoryLedgerRepository,
        provider: MemoryProvider,
        now: Callable[[], datetime] | None = None,
        commit: Callable[[], None] | None = None,
        rollback: Callable[[], None] | None = None,
        retry_max_attempts: int = 3,
        retry_backoff_seconds: int = 30,
    ) -> None:
        self._repository = repository
        self._provider = provider
        self._now = now or (lambda: datetime.now(UTC))
        self._commit = commit or (lambda: None)
        self._rollback = rollback or (lambda: None)
        self._retry_max_attempts = retry_max_attempts
        self._retry_backoff_seconds = retry_backoff_seconds

    def create_direct(
        self,
        *,
        user_id: uuid.UUID,
        category: str,
        canonical_text: str,
        source_run_id: uuid.UUID | None = None,
    ) -> PreferenceMemoryLedger:
        category, canonical_text = self._validated(category=category, canonical_text=canonical_text)
        now = self._now()
        request_key = self._direct_request_key(
            user_id=user_id,
            source_run_id=source_run_id,
            category=category,
            canonical_text=canonical_text,
        )
        return self._persist(
            lambda: self._repository.get_or_create_direct_candidate(
                user_id=user_id,
                source_run_id=source_run_id,
                category=category,
                canonical_text=canonical_text,
                request_key=request_key,
                request_key_digest=sha256(request_key.encode()).hexdigest(),
                now=now,
            )
        )

    def create_inference_proposal(self, *, user_id: uuid.UUID, category: str, canonical_text: str) -> PreferenceMemoryLedger:
        """Model inference is locally visible only after explicit confirmation, and never calls a Provider."""
        category, canonical_text = self._validated(category=category, canonical_text=canonical_text)
        now = self._now()
        ledger = PreferenceMemoryLedger(id=uuid.uuid4(), user_id=user_id, category=category, source_kind="model_inference", canonical_text=canonical_text, external_memory_id=None, is_active=False, created_at=now, updated_at=now, deleted_at=None)
        return self._persist(lambda: self._repository.add_ledger(ledger))

    def confirm_inference(self, *, memory_id: uuid.UUID, user_id: uuid.UUID) -> PreferenceMemoryLedger:
        ledger = self._repository.get_for_user(ledger_id=memory_id, user_id=user_id)
        if ledger is None or ledger.deleted_at is not None or ledger.source_kind != "model_inference" or ledger.is_active:
            raise MemoryUnavailable("memory inference is unavailable")
        external_id = self._provider.create(user_id=user_id, category=ledger.category, canonical_text=ledger.canonical_text)
        ledger.external_memory_id = external_id
        ledger.is_active = True
        ledger.updated_at = self._now()
        return self._persist(lambda: ledger)

    def list_memories(self, *, user_id: uuid.UUID) -> list[PreferenceMemoryLedger]:
        return self._repository.list_active_for_user(user_id=user_id)

    def get_memory(self, *, memory_id: uuid.UUID, user_id: uuid.UUID) -> PreferenceMemoryLedger:
        ledger = self._repository.get_active_for_user(ledger_id=memory_id, user_id=user_id)
        if ledger is None:
            raise MemoryUnavailable("memory is unavailable")
        return ledger

    def update_memory(self, *, memory_id: uuid.UUID, user_id: uuid.UUID, canonical_text: str) -> PreferenceMemoryLedger:
        ledger = self._repository.get_active_for_user(ledger_id=memory_id, user_id=user_id, for_update=True)
        if ledger is None:
            raise MemoryUnavailable("memory is unavailable")
        _category, canonical_text = self._validated(category=ledger.category, canonical_text=canonical_text)
        if ledger.external_memory_id is None:
            ledger.external_memory_id = self._provider.create(user_id=user_id, category=ledger.category, canonical_text=canonical_text)
        else:
            self._provider.update(user_id=user_id, external_id=ledger.external_memory_id, category=ledger.category, canonical_text=canonical_text)
        ledger.canonical_text = canonical_text
        ledger.source_kind = "user_maintained"
        ledger.updated_at = self._now()
        return self._persist(lambda: ledger)

    def delete_memory(self, *, memory_id: uuid.UUID, user_id: uuid.UUID) -> None:
        ledger = self._repository.get_active_for_user(ledger_id=memory_id, user_id=user_id, for_update=True)
        if ledger is None:
            raise MemoryUnavailable("memory is unavailable")
        now = self._now()
        ledger.is_active = False
        ledger.deleted_at = now
        ledger.updated_at = now
        if self._repository.cancel_pending_provision(
            ledger_id=ledger.id, user_id=user_id, now=now
        ):
            ledger.provisioning_status = "cancelled"
        else:
            provision = self._repository.get_provision_for_ledger(
                ledger_id=ledger.id, user_id=user_id
            )
            if ledger.external_memory_id is not None or provision is not None:
                self._repository.add_outbox(
                    MemoryDeletionOutbox(
                        id=uuid.uuid4(),
                        user_id=user_id,
                        ledger_id=ledger.id,
                        operation="delete_external_memory",
                        request_key=provision.request_key if provision is not None else None,
                        attempt=0,
                        not_before=now,
                        status="pending",
                        created_at=now,
                        updated_at=now,
                        deleted_at=None,
                    )
                )
        self._persist(lambda: None)

    def process_due_deletions(self) -> tuple[int, int]:
        """Run by the lifecycle worker. Local invisibility has already committed before this I/O."""
        succeeded = failed = 0
        for outbox in self._repository.list_due_outbox(due_at=self._now()):
            ledger = self._repository.get_for_user(ledger_id=outbox.ledger_id, user_id=outbox.user_id)
            now = self._now()
            try:
                if ledger is not None and ledger.external_memory_id is not None:
                    self._provider.delete(user_id=outbox.user_id, external_id=ledger.external_memory_id)
                outbox.status = "completed"
                outbox.updated_at = now
                self._persist(lambda: None)
                succeeded += 1
            except Exception:
                outbox.attempt += 1
                outbox.updated_at = now
                if outbox.attempt >= self._retry_max_attempts:
                    outbox.status = "failed"
                else:
                    outbox.not_before = now + timedelta(seconds=self._retry_backoff_seconds * (2 ** (outbox.attempt - 1)))
                self._persist(lambda: None)
                failed += 1
        return succeeded, failed

    @staticmethod
    def _validated(*, category: str, canonical_text: str) -> tuple[str, str]:
        normalized = " ".join(canonical_text.split())
        if category not in ALLOWED_CATEGORIES or not normalized:
            raise MemoryValidationError("invalid preference memory")
        return category, normalized

    @staticmethod
    def _direct_request_key(
        *,
        user_id: uuid.UUID,
        source_run_id: uuid.UUID | None,
        category: str,
        canonical_text: str,
    ) -> str:
        """Opaque stable key: persistence never stores the user sentence as provenance."""
        canonical_digest = sha256(canonical_text.encode()).hexdigest()
        source = str(source_run_id) if source_run_id is not None else "manual"
        return sha256(
            f"direct-memory.v1|{user_id}|{source}|{category}|{canonical_digest}".encode()
        ).hexdigest()

    def _persist(self, operation: Callable[[], object]):
        try:
            result = operation()
            self._commit()
            return result
        except Exception:
            self._rollback()
            raise
