"""Local-ledger authorization, source audit and retryable external-memory deletion."""

from __future__ import annotations

import uuid
import re
from hashlib import sha256
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from app.memory.ports import MemoryLedgerRepository, MemoryProvider, MemoryReplicaMissing
from app.records.models import PreferenceMemoryLedger


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

    def capture_explicit_preferences(
        self, *, user_id: uuid.UUID, source_run_id: uuid.UUID, statement: str
    ) -> list[PreferenceMemoryLedger]:
        """Persist only deterministic first-person statements; guesses stay proposals."""
        captured: list[PreferenceMemoryLedger] = []
        for category, canonical_text in self._extract_explicit_preferences(statement):
            ledger = self.create_direct(
                user_id=user_id,
                source_run_id=source_run_id,
                category=category,
                canonical_text=canonical_text,
            )
            captured.append(ledger)
        return captured

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
            try:
                self._provider.update(user_id=user_id, external_id=ledger.external_memory_id, category=ledger.category, canonical_text=canonical_text)
            except MemoryReplicaMissing:
                # The locked, owner-checked ledger remains authoritative when an
                # ephemeral fake loses its replica. Unknown outcomes must not create duplicates.
                ledger.external_memory_id = self._provider.create(user_id=user_id, category=ledger.category, canonical_text=canonical_text)
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
                self._repository.ensure_deletion_intent(
                    ledger_id=ledger.id,
                    user_id=user_id,
                    request_key=provision.request_key if provision is not None else None,
                    now=now,
                )
        self._persist(lambda: None)

    def process_due_deletions(self) -> tuple[int, int]:
        """Run by the lifecycle worker. Local invisibility has already committed before this I/O."""
        succeeded = failed = 0
        for outbox in self._repository.list_due_outbox(due_at=self._now()):
            ledger = self._repository.get_for_user(ledger_id=outbox.ledger_id, user_id=outbox.user_id)
            now = self._now()
            try:
                external_id = ledger.external_memory_id if ledger is not None else None
                if external_id is None and outbox.request_key is not None:
                    external_id = self._provider.resolve_direct_by_request_key(
                        user_id=outbox.user_id, request_key=outbox.request_key
                    )
                if external_id is not None:
                    self._provider.delete(user_id=outbox.user_id, external_id=external_id)
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

    def process_due_provisioning(self) -> tuple[int, int]:
        """Perform durable provider work outside locks; a deleted ledger can never reactivate."""
        succeeded = failed = 0
        while True:
            claimed = self._persist(
                lambda: self._repository.claim_due_provisioning(
                    due_at=self._now(), now=self._now()
                )
            )
            if claimed is None:
                break
            intent, previous_status = claimed
            provision_id, user_id = intent.id, intent.user_id
            prepared = self._persist(
                lambda: self._repository.recheck_claimed_provision(
                    provision_id=provision_id, user_id=user_id, now=self._now()
                )
            )
            if prepared is None:
                continue
            ledger, intent = prepared
            try:
                external_id = self._provider.resolve_direct_by_request_key(
                    user_id=user_id, request_key=intent.request_key
                )
                # An outcome-unknown retry may only resolve its opaque request key.  Retrying a
                # blind create here would turn a timeout into an unbounded duplicate-write bug.
                if external_id is None and previous_status != "outcome_unknown":
                    external_id = self._provider.create_direct(
                        user_id=user_id,
                        category=ledger.category,
                        canonical_text=ledger.canonical_text,
                        request_key=intent.request_key,
                    )
                if external_id is None:
                    raise TimeoutError("direct provider outcome remains unknown")
            except Exception:
                self._persist(
                    lambda: self._repository.record_provision_unknown(
                        provision_id=provision_id,
                        user_id=user_id,
                        now=self._now(),
                        retry_max_attempts=self._retry_max_attempts,
                        retry_backoff_seconds=self._retry_backoff_seconds,
                    )
                )
                failed += 1
                continue
            self._persist(
                lambda: self._repository.bind_provision_or_schedule_deletion(
                    provision_id=provision_id,
                    user_id=user_id,
                    external_id=external_id,
                    now=self._now(),
                )
            )
            succeeded += 1
        return succeeded, failed

    @staticmethod
    def _validated(*, category: str, canonical_text: str) -> tuple[str, str]:
        normalized = " ".join(canonical_text.split())
        if category not in ALLOWED_CATEGORIES or not normalized:
            raise MemoryValidationError("invalid preference memory")
        return category, normalized

    @staticmethod
    def _extract_explicit_preferences(statement: str) -> list[tuple[str, str]]:
        """D-08 allowlist intentionally rejects model, image and meal-parser observations."""
        clauses = (" ".join(part.split()).strip() for part in re.split(r"[，,。！!?；;]", statement))
        for normalized in clauses:
            avoidance = re.fullmatch(r"(?:我|今天)?(?:不想|不)吃(?P<item>.+)", normalized)
            if avoidance is not None:
                item = avoidance.group("item").strip()
                return [("avoidance", f"不吃{item}")] if item else []
            goal = re.fullmatch(r"(?:我的)?目标(?:是|为)(?P<value>.+)", normalized)
            if goal is not None and goal.group("value").strip():
                return [("goal", goal.group("value").strip())]
            preference = re.fullmatch(r"我(?:喜欢|偏好)(?P<value>.+)", normalized)
            if preference is not None and preference.group("value").strip():
                return [("stable_preference", preference.group("value").strip())]
        return []

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
