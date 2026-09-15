"""Long-term preference memory behaviour over local in-memory fakes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.memory.providers import FakeMemoryProvider
from app.memory.providers import create_memory_provider
from app.memory.service import MemoryService, MemoryUnavailable
from app.core.config import ConfigurationError, Settings
from app.records.models import MemoryDeletionOutbox, MemoryProvisionOutbox, PreferenceMemoryLedger


NOW = datetime(2026, 8, 31, 8, 0, tzinfo=UTC)


class FakeMemoryLedgerRepository:
    def __init__(self) -> None:
        self.ledgers: dict[uuid.UUID, PreferenceMemoryLedger] = {}
        self.outbox: list[MemoryDeletionOutbox] = []
        self.provision_outbox: list[MemoryProvisionOutbox] = []

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
        for ledger in self.ledgers.values():
            if (
                ledger.user_id == user_id
                and ledger.category == category
                and ledger.canonical_text == canonical_text
                and ledger.is_active
                and ledger.deleted_at is None
            ):
                return ledger
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
        self.ledgers[ledger.id] = ledger
        self.provision_outbox.append(
            MemoryProvisionOutbox(
                id=uuid.uuid4(),
                user_id=user_id,
                ledger_id=ledger.id,
                operation="provision_external_memory",
                request_key=request_key,
                attempt=0,
                not_before=now,
                status="pending",
                created_at=now,
                updated_at=now,
                deleted_at=None,
            )
        )
        return ledger

    def cancel_pending_provision(
        self, *, ledger_id: uuid.UUID, user_id: uuid.UUID, now: datetime
    ) -> bool:
        for intent in self.provision_outbox:
            if intent.ledger_id == ledger_id and intent.user_id == user_id and intent.status == "pending":
                intent.status = "cancelled"
                intent.updated_at = now
                return True
        return False

    def get_provision_for_ledger(
        self, *, ledger_id: uuid.UUID, user_id: uuid.UUID
    ) -> MemoryProvisionOutbox | None:
        return next(
            (
                intent
                for intent in self.provision_outbox
                if intent.ledger_id == ledger_id and intent.user_id == user_id
            ),
            None,
        )

    def list_due_provisioning(self, *, due_at: datetime) -> list[MemoryProvisionOutbox]:
        return [
            intent
            for intent in self.provision_outbox
            if intent.status in {"pending", "outcome_unknown"} and intent.not_before <= due_at
        ]

    def claim_due_provisioning(
        self, *, due_at: datetime, now: datetime
    ) -> tuple[MemoryProvisionOutbox, str] | None:
        for intent in self.list_due_provisioning(due_at=due_at):
            ledger = self.ledgers[intent.ledger_id]
            if not ledger.is_active or ledger.deleted_at is not None:
                intent.status = "cancelled"
                ledger.provisioning_status = "cancelled"
                continue
            previous_status = intent.status
            intent.status = "claimed"
            intent.claimed_at = now
            ledger.provisioning_status = "claimed"
            return intent, previous_status
        return None

    def recheck_claimed_provision(
        self, *, provision_id: uuid.UUID, user_id: uuid.UUID, now: datetime
    ) -> tuple[PreferenceMemoryLedger, MemoryProvisionOutbox] | None:
        intent = next(intent for intent in self.provision_outbox if intent.id == provision_id)
        ledger = self.ledgers[intent.ledger_id]
        if intent.user_id != user_id or not ledger.is_active or ledger.deleted_at is not None:
            intent.status = "cancelled"
            ledger.provisioning_status = "cancelled"
            return None
        return ledger, intent

    def bind_provision_or_schedule_deletion(
        self, *, provision_id: uuid.UUID, user_id: uuid.UUID, external_id: str, now: datetime
    ) -> bool:
        intent = next(intent for intent in self.provision_outbox if intent.id == provision_id)
        ledger = self.ledgers[intent.ledger_id]
        intent.status = "provisioned"
        if intent.user_id != user_id or not ledger.is_active or ledger.deleted_at is not None:
            self.ensure_deletion_intent(
                ledger_id=ledger.id, user_id=user_id, request_key=intent.request_key, now=now
            )
            return False
        ledger.external_memory_id = external_id
        ledger.provisioning_status = "provisioned"
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
        intent = next(intent for intent in self.provision_outbox if intent.id == provision_id)
        ledger = self.ledgers[intent.ledger_id]
        if intent.user_id != user_id or not ledger.is_active or ledger.deleted_at is not None:
            intent.status = "cancelled"
            ledger.provisioning_status = "cancelled"
            return
        intent.attempt += 1
        intent.status = "failed" if intent.attempt >= retry_max_attempts else "outcome_unknown"
        intent.not_before = now + timedelta(seconds=retry_backoff_seconds * (2 ** (intent.attempt - 1)))
        ledger.provisioning_status = intent.status

    def ensure_deletion_intent(
        self, *, ledger_id: uuid.UUID, user_id: uuid.UUID, request_key: str | None, now: datetime
    ) -> MemoryDeletionOutbox:
        existing = next((outbox for outbox in self.outbox if outbox.ledger_id == ledger_id), None)
        if existing is not None:
            existing.status = "pending"
            existing.request_key = request_key or existing.request_key
            existing.not_before = now
            return existing
        outbox = MemoryDeletionOutbox(
            id=uuid.uuid4(), user_id=user_id, ledger_id=ledger_id,
            operation="delete_external_memory", request_key=request_key, attempt=0,
            not_before=now, status="pending", created_at=now, updated_at=now, deleted_at=None,
        )
        self.outbox.append(outbox)
        return outbox

    def list_due_outbox(self, *, due_at: datetime) -> list[MemoryDeletionOutbox]:
        return [outbox for outbox in self.outbox if outbox.status == "pending" and outbox.not_before <= due_at]


def _service(repo: FakeMemoryLedgerRepository, provider: FakeMemoryProvider) -> MemoryService:
    return MemoryService(repository=repo, provider=provider, now=lambda: NOW, retry_backoff_seconds=1)


def test_direct_statement_creates_active_audited_memory_and_inference_waits_for_confirmation() -> None:
    repository, provider, user_id = FakeMemoryLedgerRepository(), FakeMemoryProvider(), uuid.uuid4()
    service = _service(repository, provider)
    direct = service.create_direct(user_id=user_id, source_run_id=uuid.uuid4(), category="avoidance", canonical_text="  今天 不吃 辣  ")
    proposal = service.create_inference_proposal(user_id=user_id, category="goal", canonical_text="控制体重")
    assert direct.is_active and direct.source_kind == "user_statement" and direct.canonical_text == "今天 不吃 辣"
    assert proposal.is_active is False and proposal.external_memory_id is None
    assert provider.calls == []
    confirmed = service.confirm_inference(memory_id=proposal.id, user_id=user_id)
    assert confirmed.is_active and confirmed.external_memory_id is not None and [call.operation for call in provider.calls] == ["create"]


def test_foreign_memory_id_never_reaches_provider_and_edit_is_user_maintained() -> None:
    repository, provider = FakeMemoryLedgerRepository(), FakeMemoryProvider()
    owner, other = uuid.uuid4(), uuid.uuid4()
    service = _service(repository, provider)
    memory = service.create_direct(user_id=owner, source_run_id=uuid.uuid4(), category="stable_preference", canonical_text="早餐喜欢清淡")
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
    proposal = service.create_inference_proposal(user_id=user_id, category="avoidance", canonical_text="不吃花生")
    memory = service.confirm_inference(memory_id=proposal.id, user_id=user_id)
    provider.fail_next_delete = True
    service.delete_memory(memory_id=memory.id, user_id=user_id)
    assert service.list_memories(user_id=user_id) == [] and len(repository.outbox) == 1
    assert service.process_due_deletions() == (0, 1)
    assert repository.outbox[0].status == "pending" and repository.outbox[0].attempt == 1
    repository.outbox[0].not_before = NOW
    assert service.process_due_deletions() == (1, 0)
    assert repository.outbox[0].status == "completed"


def test_edit_recovers_a_lost_fake_replica_after_authorizing_the_ledger() -> None:
    repository, provider, owner = FakeMemoryLedgerRepository(), FakeMemoryProvider(), uuid.uuid4()
    service = _service(repository, provider)
    memory = service.create_direct(user_id=owner, category="avoidance", canonical_text="不吃辣")
    service.process_due_provisioning()
    old_external_id = memory.external_memory_id
    restarted = FakeMemoryProvider()
    service = _service(repository, restarted)
    with pytest.raises(MemoryUnavailable):
        service.update_memory(memory_id=memory.id, user_id=uuid.uuid4(), canonical_text="他人修改")
    assert restarted.calls == []
    updated = service.update_memory(memory_id=memory.id, user_id=owner, canonical_text="不吃辣 饮食清淡")
    assert updated.id == memory.id
    assert updated.canonical_text == "不吃辣 饮食清淡"
    assert updated.source_kind == "user_maintained"
    assert updated.external_memory_id != old_external_id
    assert [call.operation for call in restarted.calls] == ["create"]
    assert restarted.search(user_id=owner, query="清淡", limit=3)[0].canonical_text == updated.canonical_text


@pytest.mark.parametrize("failure", [TimeoutError, LookupError])
def test_edit_never_recreates_on_unknown_failure_or_owner_mismatch(failure) -> None:
    class FailingUpdate(FakeMemoryProvider):
        def update(self, **kwargs):
            raise failure("unavailable")

    repository, provider, owner = FakeMemoryLedgerRepository(), FailingUpdate(), uuid.uuid4()
    service = _service(repository, provider)
    memory = service.create_direct(user_id=owner, category="avoidance", canonical_text="不吃辣")
    service.process_due_provisioning()
    calls_before, external_id = list(provider.calls), memory.external_memory_id
    with pytest.raises(failure):
        service.update_memory(memory_id=memory.id, user_id=owner, canonical_text="清淡")
    assert provider.calls == calls_before
    assert memory.canonical_text == "不吃辣" and memory.external_memory_id == external_id


def test_fake_replica_ids_do_not_collide_across_instances_or_after_deletion() -> None:
    owner = uuid.uuid4()
    first, second = FakeMemoryProvider(), FakeMemoryProvider()
    ids = [first.create(user_id=owner, category="avoidance", canonical_text="不吃辣")]
    ids.append(second.create(user_id=owner, category="avoidance", canonical_text="不吃辣"))
    first.delete(user_id=owner, external_id=ids[0])
    ids.append(first.create(user_id=owner, category="avoidance", canonical_text="清淡"))
    assert len(set(ids)) == 3


def test_mem0_mode_fails_closed_without_its_required_secret_and_endpoint() -> None:
    with pytest.raises(ConfigurationError, match="MEM0_API_KEY"):
        create_memory_provider(Settings(app_env="local", memory_provider_mode="mem0", _env_file=None))


def test_direct_preference_creates_auditable_pending_provision_without_provider_call() -> None:
    repository, provider, user_id = FakeMemoryLedgerRepository(), FakeMemoryProvider(), uuid.uuid4()
    service = _service(repository, provider)

    memory = service.create_direct(
        user_id=user_id,
        source_run_id=uuid.uuid4(),
        category="avoidance",
        canonical_text="不吃辣",
    )

    assert memory.source_kind == "user_statement"
    assert memory.provisioning_status == "pending"
    assert memory.source_run_id is not None
    assert memory.request_key_digest is not None
    assert len(repository.provision_outbox) == 1
    assert provider.calls == []


def test_direct_preference_is_idempotent_across_runs_but_isolated_by_user() -> None:
    repository, provider, user_id = FakeMemoryLedgerRepository(), FakeMemoryProvider(), uuid.uuid4()
    service = _service(repository, provider)
    source_run_id = uuid.uuid4()

    first = service.create_direct(user_id=user_id, source_run_id=source_run_id, category="avoidance", canonical_text="不吃辣")
    repeated_same_run = service.create_direct(user_id=user_id, source_run_id=source_run_id, category="avoidance", canonical_text="不吃辣")
    repeated_new_run = service.create_direct(user_id=user_id, source_run_id=uuid.uuid4(), category="avoidance", canonical_text="不吃辣")
    other_user = service.create_direct(user_id=uuid.uuid4(), source_run_id=uuid.uuid4(), category="avoidance", canonical_text="不吃辣")

    assert first.id == repeated_same_run.id == repeated_new_run.id
    assert other_user.id != first.id
    assert len(repository.provision_outbox) == 2
    assert provider.calls == []


def test_delete_cancels_unclaimed_provision_without_provider_call() -> None:
    repository, provider, user_id = FakeMemoryLedgerRepository(), FakeMemoryProvider(), uuid.uuid4()
    service = _service(repository, provider)
    memory = service.create_direct(user_id=user_id, source_run_id=uuid.uuid4(), category="avoidance", canonical_text="不吃辣")

    service.delete_memory(memory_id=memory.id, user_id=user_id)

    assert memory.is_active is False
    assert memory.provisioning_status == "cancelled"
    assert [intent.status for intent in repository.provision_outbox] == ["cancelled"]
    assert provider.calls == []


def test_explicit_preference_capture_uses_allowlist_and_single_infer_false_record() -> None:
    repository, provider, user_id = FakeMemoryLedgerRepository(), FakeMemoryProvider(), uuid.uuid4()
    service = _service(repository, provider)

    memories = service.capture_explicit_preferences(
        user_id=user_id,
        source_run_id=uuid.uuid4(),
        statement="我不吃辣",
    )
    temporary = service.capture_explicit_preferences(
        user_id=user_id,
        source_run_id=uuid.uuid4(),
        statement="今天不想吃辣",
    )
    rejected = service.capture_explicit_preferences(
        user_id=user_id,
        source_run_id=uuid.uuid4(),
        statement="图片里看起来没有辣椒",
    )

    assert [(memory.category, memory.canonical_text) for memory in memories] == [("avoidance", "不吃辣")]
    assert [memory.id for memory in temporary] == [memories[0].id]
    assert rejected == []
    assert provider.calls == []
    assert service.process_due_provisioning() == (1, 0)
    assert [(call.operation, call.infer) for call in provider.calls] == [("resolve_direct", None), ("create_direct", False)]
    assert provider.direct_records == {
        provider.calls[-1].request_key: (user_id, "avoidance", "不吃辣", False)
    }


def test_direct_provision_retry_resolves_exact_request_key_before_creating_again() -> None:
    repository, provider, user_id = FakeMemoryLedgerRepository(), FakeMemoryProvider(), uuid.uuid4()
    service = _service(repository, provider)
    memory = service.create_direct(
        user_id=user_id,
        source_run_id=uuid.uuid4(),
        category="avoidance",
        canonical_text="不吃辣",
    )
    intent = repository.provision_outbox[0]
    provider.create_direct(
        user_id=user_id,
        category="avoidance",
        canonical_text="不吃辣",
        request_key=intent.request_key,
    )

    assert service.process_due_provisioning() == (1, 0)
    assert memory.provisioning_status == "provisioned"
    assert [call.operation for call in provider.calls] == ["create_direct", "resolve_direct"]


def test_mem0_direct_adapter_fails_closed_when_add_is_not_exactly_one_id() -> None:
    from app.memory.providers import Mem0MemoryProvider

    class StubClient:
        def add(self, **_kwargs: object) -> dict[str, object]:
            return {"results": [{"id": "first"}, {"id": "second"}]}

    provider = object.__new__(Mem0MemoryProvider)
    provider._client = StubClient()  # type: ignore[attr-defined]
    with pytest.raises(RuntimeError, match="exactly one"):
        provider.create_direct(
            user_id=uuid.uuid4(),
            category="avoidance",
            canonical_text="不吃辣",
            request_key="opaque-key",
        )


def test_mem0_direct_adapter_passes_exact_canonical_record_without_inference() -> None:
    from app.memory.providers import Mem0MemoryProvider

    class StubClient:
        def __init__(self) -> None:
            self.kwargs: dict[str, object] | None = None

        def add(self, **kwargs: object) -> dict[str, object]:
            self.kwargs = kwargs
            return {"results": [{"id": "canonical-id"}]}

    client = StubClient()
    provider = object.__new__(Mem0MemoryProvider)
    provider._client = client  # type: ignore[attr-defined]
    user_id = uuid.uuid4()

    assert provider.create_direct(
        user_id=user_id,
        category="avoidance",
        canonical_text="不吃辣",
        request_key="opaque-key",
    ) == "canonical-id"
    assert client.kwargs == {
        "messages": [{"role": "user", "content": "不吃辣"}],
        "user_id": str(user_id),
        "metadata": {
            "category": "avoidance",
            "source": "food-agent-direct.v1",
            "request_key": "opaque-key",
        },
        "infer": False,
    }
