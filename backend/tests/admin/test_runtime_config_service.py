"""RED contracts for immutable, non-secret reasoning runtime configuration."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.admin.schemas import RuntimeConfigCommand
from app.admin.service import AdminPermissionDenied, AdminService, RuntimeAdmissionDenied, RuntimeConfigConflict
from app.agent.models import AgentRun, AgentThread
from app.agent.ports import RuntimeConfigAdmission
from app.agent.service import AgentService
from app.agent.state import AgentGraphKind
from app.auth.models import User, UserRole
from app.core.config import ConfigurationError, Settings
from app.providers.reasoning.factory import create_reasoning_provider


NOW = datetime(2026, 9, 3, tzinfo=UTC)


def _admin(role: str = UserRole.ADMIN.value) -> User:
    return User(
        id=uuid.uuid4(), email="runtime-admin@example.com", password_hash="hash", role=role,
        is_active=True, email_verified_at=NOW, created_at=NOW, updated_at=NOW,
    )


class FakeRuntimeConfigRepository:
    """Small fake proves service policy without a Provider, key, or network."""

    def __init__(self, user: User) -> None:
        self.user = user
        self.versions: list[object] = []
        self.commands: dict[str, object] = {}
        self.events: list[object] = []
        self.locked = 0

    def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.user if self.user.id == user_id else None

    def acquire_runtime_config_lock(self) -> None:
        self.locked += 1

    def get_runtime_config_command(self, command_key: str) -> object | None:
        return self.commands.get(command_key)

    def get_active_runtime_config(self) -> object | None:
        return self.versions[-1] if self.versions else None

    def next_runtime_config_version(self) -> int:
        return len(self.versions) + 1

    def add_runtime_config_version(self, version: object) -> object:
        self.versions.append(version)
        self.commands[getattr(version, "command_key")] = version
        return version

    def add_audit_event(self, event: object) -> object:
        self.events.append(event)
        return event


class FakeAgentRepository:
    def __init__(self, thread: AgentThread) -> None:
        self.thread = thread
        self.runs: dict[str, AgentRun] = {}

    def get_thread_for_user(self, *, thread_id: uuid.UUID, user_id: uuid.UUID, for_update: bool = False) -> AgentThread | None:
        return self.thread if (thread_id, user_id) == (self.thread.id, self.thread.user_id) else None

    def get_run_for_command_for_user(self, *, thread_id: uuid.UUID, user_id: uuid.UUID, command_key: str, for_update: bool = False) -> AgentRun | None:
        return self.runs.get(command_key)

    def add_run(self, run: AgentRun) -> AgentRun:
        self.runs[run.command_key] = run
        return run


class FakeRuntimeConfigAdmitter:
    def __init__(self, admission: RuntimeConfigAdmission) -> None:
        self.admission = admission
        self.calls = 0

    def admit_runtime_call(self) -> RuntimeConfigAdmission:
        self.calls += 1
        return self.admission


def _command(**overrides: object) -> RuntimeConfigCommand:
    payload: dict[str, object] = {
        "provider": "deepseek", "model_alias": "deepseek-v4-flash", "enabled": True,
        "single_call_cap_usd": Decimal("0.03"), "period_cap_usd": Decimal("3.00"),
        "input_usd_per_m": Decimal("0.20"), "output_usd_per_m": Decimal("0.80"),
        "reason": "price and safety limits reviewed", "confirm": True,
    }
    return RuntimeConfigCommand(**(payload | overrides))


def test_runtime_config_command_is_strict_allowlisted_and_never_accepts_secrets() -> None:
    payload = _command().model_dump()
    with pytest.raises(ValidationError):
        RuntimeConfigCommand(**(payload | {"api_key": "not-allowed"}))
    with pytest.raises(ValidationError):
        RuntimeConfigCommand(**(payload | {"endpoint": "https://attacker.invalid"}))
    with pytest.raises(ValidationError):
        _command(model_alias="arbitrary-model")
    with pytest.raises(ValidationError):
        _command(reason=" ")


def test_admin_versioning_is_immutable_idempotent_and_uses_current_db_role() -> None:
    actor = _admin()
    repository = FakeRuntimeConfigRepository(actor)
    service = AdminService(repository=repository, now=lambda: NOW)

    first = service.configure_runtime(actor_user_id=actor.id, command=_command(), command_key="runtime-config-0001")
    replay = service.configure_runtime(actor_user_id=actor.id, command=_command(), command_key="runtime-config-0001")
    disabled = service.configure_runtime(
        actor_user_id=actor.id, command=_command(enabled=False, reason="provider disabled for incident"), command_key="runtime-config-0002",
    )

    assert first.version == 1
    assert replay.id == first.id
    assert disabled.version == 2
    assert first.enabled is True  # a later command must not rewrite an in-flight snapshot
    assert repository.locked == 3  # replays lock too, so idempotency is race-safe
    assert len(repository.events) == 2
    assert service.read_runtime_config(actor_user_id=actor.id).id == disabled.id
    with pytest.raises(RuntimeConfigConflict):
        service.configure_runtime(
            actor_user_id=actor.id, command=_command(reason="stale browser edit"),
            command_key="runtime-config-0006", expected_version=1,
        )
    repository.user = _admin(UserRole.USER.value)
    with pytest.raises(AdminPermissionDenied):
        service.configure_runtime(actor_user_id=repository.user.id, command=_command(), command_key="runtime-config-0003")
    with pytest.raises(AdminPermissionDenied):
        service.configure_runtime(actor_user_id=repository.user.id, command=_command(), command_key="runtime-config-0001")


def test_admission_blocks_disabled_or_over_budget_new_calls_without_replaying_unknown_outcome() -> None:
    actor = _admin()
    repository = FakeRuntimeConfigRepository(actor)
    service = AdminService(repository=repository, now=lambda: NOW)
    enabled = service.configure_runtime(actor_user_id=actor.id, command=_command(), command_key="runtime-config-0004")
    snapshot = service.admit_runtime_call()
    assert snapshot.version_id == enabled.id
    assert snapshot.snapshot["model_alias"] == "deepseek-v4-flash"
    service.configure_runtime(actor_user_id=actor.id, command=_command(enabled=False, reason="incident stop"), command_key="runtime-config-0005")
    with pytest.raises(RuntimeAdmissionDenied):
        service.admit_runtime_call()
    assert snapshot.snapshot["enabled"] is True  # already admitted work retains the old immutable policy


def test_agent_service_injects_admission_before_new_run_and_reuses_existing_snapshot() -> None:
    user_id = uuid.uuid4()
    thread = AgentThread(
        id=uuid.uuid4(), user_id=user_id, status="open", revision=0,
        created_at=NOW, last_activity_at=NOW, deleted_at=None,
    )
    admission = RuntimeConfigAdmission(
        version_id=uuid.uuid4(),
        snapshot={
            "version": 1, "provider": "deepseek", "model_alias": "deepseek-v4-flash", "enabled": True,
            "single_call_cap_usd": "0.03", "period_cap_usd": "3.00",
            "input_usd_per_m": "0.20", "output_usd_per_m": "0.80",
        },
    )
    admitter = FakeRuntimeConfigAdmitter(admission)
    service = AgentService(
        repository=FakeAgentRepository(thread), now=lambda: NOW, runtime_config_admitter=admitter,
    )

    created = service.create_or_reuse_run(
        thread_id=thread.id, user_id=user_id, command_key="runtime-command-0001",
        canonical_command={"kind": "description", "input_hash": "a"}, graph_kind=AgentGraphKind.MEAL_ANALYSIS,
    )
    replay = service.create_or_reuse_run(
        thread_id=thread.id, user_id=user_id, command_key="runtime-command-0001",
        canonical_command={"kind": "description", "input_hash": "a"}, graph_kind=AgentGraphKind.MEAL_ANALYSIS,
    )

    assert created.runtime_config_version_id == admission.version_id
    assert created.runtime_config_snapshot == admission.snapshot
    assert replay is created
    assert admitter.calls == 1  # a replay cannot be blocked by a later disable version


def test_provider_factory_accepts_only_safe_snapshot_and_resolves_key_from_environment_settings() -> None:
    settings = Settings(
        app_env="local", reasoning_provider_mode="deepseek", deepseek_api_key="environment-only-key",
        deepseek_model="deepseek-v4-flash", deepseek_price_snapshot_version="pricing-v1",
        deepseek_input_usd_per_m=Decimal("0.20"), deepseek_output_usd_per_m=Decimal("0.80"),
    )
    provider = create_reasoning_provider(
        settings,
        runtime_config={
            "version": 1, "provider": "deepseek", "model_alias": "deepseek-v4-flash", "enabled": True,
            "single_call_cap_usd": "0.03", "period_cap_usd": "3.00",
            "input_usd_per_m": "0.20", "output_usd_per_m": "0.80",
        },
    )
    assert provider.__class__.__name__ == "DeepSeekReasoningModelProvider"
    with pytest.raises(ConfigurationError):
        create_reasoning_provider(settings, runtime_config={"endpoint": "https://unsafe.invalid"})
