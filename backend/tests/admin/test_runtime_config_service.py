"""RED contracts for immutable, non-secret reasoning runtime configuration."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.admin.schemas import RuntimeConfigCommand
from app.admin.service import AdminPermissionDenied, AdminService, RuntimeAdmissionDenied
from app.auth.models import User, UserRole


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


def _command(**overrides: object) -> RuntimeConfigCommand:
    return RuntimeConfigCommand(
        provider="deepseek",
        model_alias="deepseek-v4-flash",
        enabled=True,
        single_call_cap_usd=Decimal("0.03"),
        period_cap_usd=Decimal("3.00"),
        input_usd_per_m=Decimal("0.20"),
        output_usd_per_m=Decimal("0.80"),
        reason="price and safety limits reviewed",
        confirm=True,
        **overrides,
    )


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
    assert repository.locked == 2
    assert len(repository.events) == 2
    repository.user = _admin(UserRole.USER.value)
    with pytest.raises(AdminPermissionDenied):
        service.configure_runtime(actor_user_id=repository.user.id, command=_command(), command_key="runtime-config-0003")


def test_admission_blocks_disabled_or_over_budget_new_calls_without_replaying_unknown_outcome() -> None:
    actor = _admin()
    repository = FakeRuntimeConfigRepository(actor)
    service = AdminService(repository=repository, now=lambda: NOW)
    enabled = service.configure_runtime(actor_user_id=actor.id, command=_command(), command_key="runtime-config-0004")
    snapshot = service.admit_runtime_call(actor_user_id=actor.id, worst_case_cost_usd=Decimal("0.03"))
    assert snapshot.id == enabled.id
    assert snapshot.model_alias == "deepseek-v4-flash"

    with pytest.raises(RuntimeAdmissionDenied):
        service.admit_runtime_call(actor_user_id=actor.id, worst_case_cost_usd=Decimal("0.04"))
    service.configure_runtime(actor_user_id=actor.id, command=_command(enabled=False, reason="incident stop"), command_key="runtime-config-0005")
    with pytest.raises(RuntimeAdmissionDenied):
        service.admit_runtime_call(actor_user_id=actor.id, worst_case_cost_usd=Decimal("0.01"))
    assert snapshot.enabled is True  # already admitted work retains the old immutable policy
