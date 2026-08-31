"""Meal-record application rules over an in-memory repository fake."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.agent.models import AgentEvent, AgentRun
from app.records.models import MealRecord
from app.records.service import ConsumedAtInvalid, MealRecordConfirmationUnavailable, MealRecordService, MealRecordUnavailable


NOW = datetime(2026, 8, 31, 8, 0, tzinfo=UTC)


def _run(*, user_id: uuid.UUID, thread_id: uuid.UUID, status: str = "completed") -> AgentRun:
    return AgentRun(
        id=uuid.uuid4(), user_id=user_id, thread_id=thread_id, command_key="agent-command", command_hash="a" * 64,
        status=status, graph_version="meal-agent-graph.v1", prompt_version="prompt.v1", tool_version="nutrition-tools-v1",
        model_provider=None, model_version=None, graph_steps=1, model_calls=1, tool_calls=3, elapsed_ms=1,
        estimated_cost_usd=Decimal("0"), failure_code=None, created_at=NOW, updated_at=NOW, finished_at=NOW if status == "completed" else None,
    )


def _report(*, partial: bool = False) -> dict[str, object]:
    return {
        "waiting_input": False, "is_partial": partial,
        "items": [{
            "item_id": "rice-1", "name": "米饭", "food_id": str(uuid.uuid4()), "catalog_version": "fdc-seed-v1",
            "grams": "100", "is_estimated": False, "energy_kcal": "130.0", "protein_g": "2.4", "fat_g": "0.3",
            "carbohydrate_g": "28.2", "calculation_rule_version": "per-100g-v1",
        }],
        "totals": {"energy_kcal": "130.0", "protein_g": "2.4", "fat_g": "0.3", "carbohydrate_g": "28.2"},
    }


class FakeMealRecordRepository:
    def __init__(self, *, run: AgentRun | None, report: dict[str, object] | None) -> None:
        self.run = run
        self.report = report
        self.records: list[MealRecord] = []
        self.thread_deleted = False

    def get_completed_run_for_thread_for_user(self, *, thread_id: uuid.UUID, user_id: uuid.UUID, for_update: bool = False) -> AgentRun | None:
        if self.run is None or self.run.status != "completed" or self.run.thread_id != thread_id or self.run.user_id != user_id:
            return None
        return self.run

    def get_completed_report_for_run_for_user(self, *, run_id: uuid.UUID, user_id: uuid.UUID) -> AgentEvent | None:
        if self.run is None or self.report is None or self.run.id != run_id or self.run.user_id != user_id:
            return None
        return AgentEvent(id=uuid.uuid4(), thread_id=self.run.thread_id, run_id=self.run.id, user_id=user_id, seq=2, event_type="completed", payload={"report": self.report}, safe_summary="完成", created_at=NOW)

    def get_record_for_command_for_user(self, *, command_key: str, user_id: uuid.UUID, include_deleted: bool = False) -> MealRecord | None:
        return next((record for record in self.records if record.command_key == command_key and record.user_id == user_id and (include_deleted or record.deleted_at is None)), None)

    def get_record_for_source_run_for_user(self, *, source_run_id: uuid.UUID, user_id: uuid.UUID, include_deleted: bool = False) -> MealRecord | None:
        return next((record for record in self.records if record.source_run_id == source_run_id and record.user_id == user_id and (include_deleted or record.deleted_at is None)), None)

    def add_record(self, record: MealRecord) -> MealRecord:
        self.records.append(record)
        return record

    def get_record_for_user(self, *, record_id: uuid.UUID, user_id: uuid.UUID, for_update: bool = False) -> MealRecord | None:
        return next((record for record in self.records if record.id == record_id and record.user_id == user_id and record.deleted_at is None), None)

    def list_records_for_user(self, *, user_id: uuid.UUID) -> list[MealRecord]:
        return sorted((record for record in self.records if record.user_id == user_id and record.deleted_at is None), key=lambda record: (record.consumed_at, record.id), reverse=True)


def _service(repository: FakeMealRecordRepository, commits: list[bool] | None = None) -> MealRecordService:
    return MealRecordService(repository=repository, now=lambda: NOW, commit=(lambda: commits.append(True)) if commits is not None else None)


def test_confirm_requires_the_current_users_completed_complete_report() -> None:
    owner, other, thread = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    repository = FakeMealRecordRepository(run=_run(user_id=owner, thread_id=thread), report=_report())
    with pytest.raises(MealRecordConfirmationUnavailable):
        _service(repository).confirm_from_completed_run(user_id=other, thread_id=thread, command_key="save-key-00000001", consumed_at=None)
    repository.report = _report(partial=True)
    with pytest.raises(MealRecordConfirmationUnavailable):
        _service(repository).confirm_from_completed_run(user_id=owner, thread_id=thread, command_key="save-key-00000001", consumed_at=None)
    assert repository.records == []


def test_confirm_is_idempotent_and_uses_only_completed_report_snapshot() -> None:
    user_id, thread_id = uuid.uuid4(), uuid.uuid4()
    repository = FakeMealRecordRepository(run=_run(user_id=user_id, thread_id=thread_id), report=_report())
    commits: list[bool] = []
    service = _service(repository, commits)
    first = service.confirm_from_completed_run(user_id=user_id, thread_id=thread_id, command_key="save-key-00000001", consumed_at=NOW - timedelta(hours=1))
    second = service.confirm_from_completed_run(user_id=user_id, thread_id=thread_id, command_key="save-key-00000001", consumed_at=NOW - timedelta(hours=1))
    assert first.id == second.id and len(repository.records) == 1 and commits == [True]
    assert first.energy_kcal == Decimal("130.0")
    assert first.items[0].food_reference and first.nutrition_catalog_version == "fdc-seed-v1"


def test_future_time_update_keeps_record_id_and_does_not_recalculate_snapshot() -> None:
    user_id, thread_id = uuid.uuid4(), uuid.uuid4()
    repository = FakeMealRecordRepository(run=_run(user_id=user_id, thread_id=thread_id), report=_report())
    service = _service(repository)
    record = service.confirm_from_completed_run(user_id=user_id, thread_id=thread_id, command_key="save-key-00000001", consumed_at=None)
    with pytest.raises(ConsumedAtInvalid):
        service.update_record(record_id=record.id, user_id=user_id, consumed_at=NOW + timedelta(seconds=1))
    updated = service.update_record(record_id=record.id, user_id=user_id, consumed_at=NOW - timedelta(days=2))
    assert updated.id == record.id and updated.energy_kcal == Decimal("130.0") and updated.updated_at == NOW


def test_delete_hides_record_and_items_without_deleting_agent_thread() -> None:
    user_id, thread_id = uuid.uuid4(), uuid.uuid4()
    repository = FakeMealRecordRepository(run=_run(user_id=user_id, thread_id=thread_id), report=_report())
    service = _service(repository)
    record = service.confirm_from_completed_run(user_id=user_id, thread_id=thread_id, command_key="save-key-00000001", consumed_at=None)
    service.delete_record(record_id=record.id, user_id=user_id)
    assert service.list_records(user_id=user_id) == []
    assert all(item.deleted_at == NOW for item in record.items)
    assert repository.thread_deleted is False
    with pytest.raises(MealRecordUnavailable):
        service.get_record(record_id=record.id, user_id=user_id)
