"""Long-term preference memory behaviour over local in-memory fakes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.memory.providers import FakeMemoryProvider
from app.memory.providers import create_memory_provider
from app.memory.service import MemoryService, MemoryUnavailable
from app.core.config import ConfigurationError, Settings
from app.records.models import MemoryDeletionOutbox, PreferenceMemoryLedger


NOW = datetime(2026, 8, 31, 8, 0, tzinfo=UTC)


class FakeMemoryLedgerRepository:
    def __init__(self) -> None:
        self.ledgers: dict[uuid.UUID, PreferenceMemoryLedger] = {}
        self.outbox: list[MemoryDeletionOutbox] = []

    def add_ledger(self, ledger: PreferenceMemoryLedger) -> PreferenceMemoryLedger:
        self.ledgers[ledger.id] = ledger
        return ledger

    def get_active_for_user(self, *, ledger_id: uuid.UUID, user_id: uuid.UUID, for_update: bool = False) -> PreferenceMemoryLedger | None:
        ledger = self.ledgers.get(ledger_id)
        return ledger if ledger is not None and ledger.user_id == user_id and ledger.is_active and ledger.deleted_at is None else None

    def get_for_user(self, *, ledger_id: uuid.UUID, user_id: uuid.UUID) -> PreferenceMemoryLedger | None:
        ledger = self.ledgers.get(ledger_id)
        return ledger if ledger is not None and ledger.user_id == user_id else None

    def list_active_for_user(self, *, user_id: uuid.UUID) -> list[PreferenceMemoryLedger]:
        return [ledger for ledger in self.ledgers.values() if ledger.user_id == user_id and ledger.is_active and ledger.deleted_at is None]

    def add_outbox(self, outbox: MemoryDeletionOutbox) -> MemoryDeletionOutbox:
        self.outbox.append(outbox)
        return outbox

    def list_due_outbox(self, *, due_at: datetime) -> list[MemoryDeletionOutbox]:
        return [outbox for outbox in self.outbox if outbox.status == "pending" and outbox.not_before <= due_at]


def _service(repo: FakeMemoryLedgerRepository, provider: FakeMemoryProvider) -> MemoryService:
    return MemoryService(repository=repo, provider=provider, now=lambda: NOW, retry_backoff_seconds=1)


def test_direct_statement_creates_active_audited_memory_and_inference_waits_for_confirmation() -> None:
    repository, provider, user_id = FakeMemoryLedgerRepository(), FakeMemoryProvider(), uuid.uuid4()
    service = _service(repository, provider)
    direct = service.create_direct(user_id=user_id, category="avoidance", canonical_text="  今天 不吃 辣  ")
    proposal = service.create_inference_proposal(user_id=user_id, category="goal", canonical_text="控制体重")
    assert direct.is_active and direct.source_kind == "user_statement" and direct.canonical_text == "今天 不吃 辣"
    assert proposal.is_active is False and proposal.external_memory_id is None
    assert [call.operation for call in provider.calls] == ["create"]
    confirmed = service.confirm_inference(memory_id=proposal.id, user_id=user_id)
    assert confirmed.is_active and confirmed.external_memory_id is not None and [call.operation for call in provider.calls] == ["create", "create"]


def test_foreign_memory_id_never_reaches_provider_and_edit_is_user_maintained() -> None:
    repository, provider = FakeMemoryLedgerRepository(), FakeMemoryProvider()
    owner, other = uuid.uuid4(), uuid.uuid4()
    service = _service(repository, provider)
    memory = service.create_direct(user_id=owner, category="stable_preference", canonical_text="早餐喜欢清淡")
    calls_before = list(provider.calls)
    with pytest.raises(MemoryUnavailable):
        service.update_memory(memory_id=memory.id, user_id=other, canonical_text="高蛋白")
    with pytest.raises(MemoryUnavailable):
        service.delete_memory(memory_id=memory.id, user_id=other)
    assert provider.calls == calls_before
    updated = service.update_memory(memory_id=memory.id, user_id=owner, canonical_text="早餐喜欢高蛋白")
    assert updated.source_kind == "user_maintained" and updated.canonical_text == "早餐喜欢高蛋白"


def test_delete_is_immediately_invisible_even_when_external_cleanup_retries() -> None:
    repository, provider, user_id = FakeMemoryLedgerRepository(), FakeMemoryProvider(), uuid.uuid4()
    service = _service(repository, provider)
    memory = service.create_direct(user_id=user_id, category="avoidance", canonical_text="不吃花生")
    provider.fail_next_delete = True
    service.delete_memory(memory_id=memory.id, user_id=user_id)
    assert service.list_memories(user_id=user_id) == [] and len(repository.outbox) == 1
    assert service.process_due_deletions() == (0, 1)
    assert repository.outbox[0].status == "pending" and repository.outbox[0].attempt == 1
    repository.outbox[0].not_before = NOW
    assert service.process_due_deletions() == (1, 0)
    assert repository.outbox[0].status == "completed"


def test_mem0_mode_fails_closed_without_its_required_secret_and_endpoint() -> None:
    with pytest.raises(ConfigurationError, match="MEM0_API_KEY"):
        create_memory_provider(Settings(app_env="local", memory_provider_mode="mem0", _env_file=None))
