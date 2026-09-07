"""Meal-record application rules over an in-memory repository fake."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.agent.models import AgentEvent, AgentRun
from app.records.models import DashboardTimezonePreference, MealRecord
from app.records.service import (
    ConsumedAtInvalid,
    DashboardTimeZoneAlreadyConfirmed,
    InvalidTimeZone,
    MealRecordConfirmationUnavailable,
    MealRecordService,
    MealRecordUnavailable,
)


NOW = datetime(2026, 8, 31, 8, 0, tzinfo=UTC)


def _run(
    *, user_id: uuid.UUID, thread_id: uuid.UUID, status: str = "completed"
) -> AgentRun:
    return AgentRun(
        id=uuid.uuid4(),
        user_id=user_id,
        thread_id=thread_id,
        command_key="agent-command",
        command_hash="a" * 64,
        status=status,
        graph_version="meal-agent-graph.v1",
        prompt_version="prompt.v1",
        tool_version="nutrition-tools-v1",
        model_provider=None,
        model_version=None,
        graph_steps=1,
        model_calls=1,
        tool_calls=3,
        elapsed_ms=1,
        estimated_cost_usd=Decimal("0"),
        failure_code=None,
        created_at=NOW,
        updated_at=NOW,
        finished_at=NOW if status == "completed" else None,
    )


def _report(*, partial: bool = False) -> dict[str, object]:
    return {
        "waiting_input": False,
        "is_partial": partial,
        "items": [
            {
                "item_id": "rice-1",
                "name": "米饭",
                "food_id": str(uuid.uuid4()),
                "catalog_version": "fdc-seed-v1",
                "grams": "100",
                "is_estimated": False,
                "energy_kcal": "130.0",
                "protein_g": "2.4",
                "fat_g": "0.3",
                "carbohydrate_g": "28.2",
                "calculation_rule_version": "per-100g-v1",
            }
        ],
        "totals": {
            "energy_kcal": "130.0",
            "protein_g": "2.4",
            "fat_g": "0.3",
            "carbohydrate_g": "28.2",
        },
    }


class FakeMealRecordRepository:
    def __init__(
        self, *, run: AgentRun | None, report: dict[str, object] | None
    ) -> None:
        self.run = run
        self.report = report
        self.records: list[MealRecord] = []
        self.thread_deleted = False
        self.dashboard_time_zones: dict[uuid.UUID, DashboardTimezonePreference] = {}
        self.backfill_audits: list[object] = []
        self.preference_add_calls = 0
        self.integrity_error_preference: DashboardTimezonePreference | None = None

    def get_completed_run_for_thread_for_user(
        self, *, thread_id: uuid.UUID, user_id: uuid.UUID, for_update: bool = False
    ) -> AgentRun | None:
        if (
            self.run is None
            or self.run.status != "completed"
            or self.run.thread_id != thread_id
            or self.run.user_id != user_id
        ):
            return None
        return self.run

    def get_completed_report_for_run_for_user(
        self, *, run_id: uuid.UUID, user_id: uuid.UUID
    ) -> AgentEvent | None:
        if (
            self.run is None
            or self.report is None
            or self.run.id != run_id
            or self.run.user_id != user_id
        ):
            return None
        return AgentEvent(
            id=uuid.uuid4(),
            thread_id=self.run.thread_id,
            run_id=self.run.id,
            user_id=user_id,
            seq=2,
            event_type="completed_validated",
            payload={"report": self.report},
            safe_summary="完成",
            created_at=NOW,
        )

    def get_record_for_command_for_user(
        self, *, command_key: str, user_id: uuid.UUID, include_deleted: bool = False
    ) -> MealRecord | None:
        return next(
            (
                record
                for record in self.records
                if record.command_key == command_key
                and record.user_id == user_id
                and (include_deleted or record.deleted_at is None)
            ),
            None,
        )

    def get_record_for_source_run_for_user(
        self,
        *,
        source_run_id: uuid.UUID,
        user_id: uuid.UUID,
        include_deleted: bool = False,
    ) -> MealRecord | None:
        return next(
            (
                record
                for record in self.records
                if record.source_run_id == source_run_id
                and record.user_id == user_id
                and (include_deleted or record.deleted_at is None)
            ),
            None,
        )

    def add_record(self, record: MealRecord) -> MealRecord:
        self.records.append(record)
        return record

    def get_record_for_user(
        self, *, record_id: uuid.UUID, user_id: uuid.UUID, for_update: bool = False
    ) -> MealRecord | None:
        return next(
            (
                record
                for record in self.records
                if record.id == record_id
                and record.user_id == user_id
                and record.deleted_at is None
            ),
            None,
        )

    def list_records_for_user(self, *, user_id: uuid.UUID) -> list[MealRecord]:
        return sorted(
            (
                record
                for record in self.records
                if record.user_id == user_id and record.deleted_at is None
            ),
            key=lambda record: (record.consumed_at, record.id),
            reverse=True,
        )

    def get_dashboard_time_zone_preference_for_user(
        self, *, user_id: uuid.UUID, for_update: bool = False
    ) -> DashboardTimezonePreference | None:
        return self.dashboard_time_zones.get(user_id)

    def add_dashboard_time_zone_preference(
        self, preference: DashboardTimezonePreference
    ) -> DashboardTimezonePreference:
        self.preference_add_calls += 1
        if self.integrity_error_preference is not None:
            self.dashboard_time_zones[preference.user_id] = (
                self.integrity_error_preference
            )
            self.integrity_error_preference = None
            raise IntegrityError(
                "dashboard timezone preference conflict", {}, RuntimeError("unique")
            )
        self.dashboard_time_zones[preference.user_id] = preference
        return preference

    def list_records_without_local_date_for_user(
        self, *, user_id: uuid.UUID
    ) -> list[MealRecord]:
        return [
            record
            for record in self.records
            if record.user_id == user_id and record.consumed_local_date is None
        ]

    def add_timezone_backfill_audit(self, audit: object) -> object:
        self.backfill_audits.append(audit)
        return audit


def _service(
    repository: FakeMealRecordRepository,
    commits: list[bool] | None = None,
    rollbacks: list[bool] | None = None,
) -> MealRecordService:
    return MealRecordService(
        repository=repository,
        now=lambda: NOW,
        commit=(lambda: commits.append(True)) if commits is not None else None,
        rollback=(lambda: rollbacks.append(True)) if rollbacks is not None else None,
    )


def test_confirm_requires_the_current_users_completed_complete_report() -> None:
    owner, other, thread = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    repository = FakeMealRecordRepository(
        run=_run(user_id=owner, thread_id=thread), report=_report()
    )
    with pytest.raises(MealRecordConfirmationUnavailable):
        _service(repository).confirm_from_completed_run(
            user_id=other,
            thread_id=thread,
            command_key="save-key-00000001",
            consumed_at=None,
            time_zone="UTC",
        )
    repository.report = _report(partial=True)
    with pytest.raises(MealRecordConfirmationUnavailable):
        _service(repository).confirm_from_completed_run(
            user_id=owner,
            thread_id=thread,
            command_key="save-key-00000001",
            consumed_at=None,
            time_zone="UTC",
        )
    assert repository.records == []


def test_confirm_is_idempotent_and_uses_only_completed_report_snapshot() -> None:
    user_id, thread_id = uuid.uuid4(), uuid.uuid4()
    repository = FakeMealRecordRepository(
        run=_run(user_id=user_id, thread_id=thread_id), report=_report()
    )
    commits: list[bool] = []
    service = _service(repository, commits)
    first = service.confirm_from_completed_run(
        user_id=user_id,
        thread_id=thread_id,
        command_key="save-key-00000001",
        consumed_at=NOW - timedelta(hours=1),
        time_zone="UTC",
    )
    second = service.confirm_from_completed_run(
        user_id=user_id,
        thread_id=thread_id,
        command_key="save-key-00000001",
        consumed_at=NOW - timedelta(hours=1),
        time_zone="UTC",
    )
    assert first.id == second.id and len(repository.records) == 1 and commits == [True]
    assert first.energy_kcal == Decimal("130.0")
    assert (
        first.items[0].food_reference
        and first.nutrition_catalog_version == "fdc-seed-v1"
    )


def test_confirm_persists_each_item_catalog_version_for_mixed_catalog_report() -> None:
    user_id, thread_id = uuid.uuid4(), uuid.uuid4()
    report = _report()
    report["items"].append(
        {
            "item_id": "sour-noodles-1",
            "name": "酸辣粉",
            "food_id": str(uuid.uuid4()),
            "catalog_version": "admin-publication-v1",
            "grams": "100",
            "is_estimated": False,
            "energy_kcal": "130.0",
            "protein_g": "2.0",
            "fat_g": "2.0",
            "carbohydrate_g": "27.0",
            "calculation_rule_version": "per-100g-v1",
        }
    )
    report["totals"] = {
        "energy_kcal": "260.0",
        "protein_g": "4.4",
        "fat_g": "2.3",
        "carbohydrate_g": "55.2",
    }
    repository = FakeMealRecordRepository(
        run=_run(user_id=user_id, thread_id=thread_id), report=report
    )

    record = _service(repository).confirm_from_completed_run(
        user_id=user_id,
        thread_id=thread_id,
        command_key="save-key-00000001",
        consumed_at=None,
        time_zone="UTC",
    )

    assert record.nutrition_catalog_version == "multiple-catalogs-v1"
    assert [item.nutrition_catalog_version for item in record.items] == [
        "fdc-seed-v1",
        "admin-publication-v1",
    ]


def test_future_time_update_keeps_record_id_and_does_not_recalculate_snapshot() -> None:
    user_id, thread_id = uuid.uuid4(), uuid.uuid4()
    repository = FakeMealRecordRepository(
        run=_run(user_id=user_id, thread_id=thread_id), report=_report()
    )
    service = _service(repository)
    record = service.confirm_from_completed_run(
        user_id=user_id,
        thread_id=thread_id,
        command_key="save-key-00000001",
        consumed_at=None,
        time_zone="UTC",
    )
    with pytest.raises(ConsumedAtInvalid):
        service.update_record(
            record_id=record.id,
            user_id=user_id,
            consumed_at=NOW + timedelta(seconds=1),
            time_zone="UTC",
        )
    updated = service.update_record(
        record_id=record.id,
        user_id=user_id,
        consumed_at=NOW - timedelta(days=2),
        time_zone="UTC",
    )
    assert (
        updated.id == record.id
        and updated.energy_kcal == Decimal("130.0")
        and updated.updated_at == NOW
    )


def test_delete_hides_record_and_items_without_deleting_agent_thread() -> None:
    user_id, thread_id = uuid.uuid4(), uuid.uuid4()
    repository = FakeMealRecordRepository(
        run=_run(user_id=user_id, thread_id=thread_id), report=_report()
    )
    service = _service(repository)
    record = service.confirm_from_completed_run(
        user_id=user_id,
        thread_id=thread_id,
        command_key="save-key-00000001",
        consumed_at=None,
        time_zone="UTC",
    )
    service.delete_record(record_id=record.id, user_id=user_id)
    assert service.list_records(user_id=user_id) == []
    assert all(item.deleted_at == NOW for item in record.items)
    assert repository.thread_deleted is False
    with pytest.raises(MealRecordUnavailable):
        service.get_record(record_id=record.id, user_id=user_id)


def test_submitted_iana_zone_freezes_local_date_for_create_and_edit() -> None:
    user_id, thread_id = uuid.uuid4(), uuid.uuid4()
    repository = FakeMealRecordRepository(
        run=_run(user_id=user_id, thread_id=thread_id), report=_report()
    )
    service = _service(repository)
    shanghai_midnight = datetime(2026, 8, 30, 16, 30, tzinfo=UTC)
    record = service.confirm_from_completed_run(
        user_id=user_id,
        thread_id=thread_id,
        command_key="save-key-00000001",
        consumed_at=shanghai_midnight,
        time_zone="Asia/Shanghai",
    )
    assert record.consumed_time_zone == "Asia/Shanghai"
    assert record.consumed_local_date == date(2026, 8, 31)
    assert record.local_date_source == "submitted_time_zone"

    los_angeles_midnight = datetime(2026, 8, 31, 7, 30, tzinfo=UTC)
    updated = service.update_record(
        record_id=record.id,
        user_id=user_id,
        consumed_at=los_angeles_midnight,
        time_zone="America/Los_Angeles",
    )
    assert updated.consumed_local_date == date(2026, 8, 31)
    assert updated.consumed_time_zone == "America/Los_Angeles"
    assert updated.local_date_source == "submitted_time_zone"


def test_invalid_iana_zone_is_rejected_before_any_record_is_written() -> None:
    user_id, thread_id = uuid.uuid4(), uuid.uuid4()
    repository = FakeMealRecordRepository(
        run=_run(user_id=user_id, thread_id=thread_id), report=_report()
    )
    with pytest.raises(InvalidTimeZone):
        _service(repository).confirm_from_completed_run(
            user_id=user_id,
            thread_id=thread_id,
            command_key="save-key-00000001",
            consumed_at=NOW - timedelta(hours=1),
            time_zone="Mars/Olympus_Mons",
        )
    assert repository.records == []


def test_confirmed_dashboard_timezone_backfills_only_owned_legacy_rows_once() -> None:
    owner, other = uuid.uuid4(), uuid.uuid4()
    owner_repository = FakeMealRecordRepository(run=None, report=None)
    legacy_owner = MealRecord(
        id=uuid.uuid4(),
        user_id=owner,
        source_run_id=uuid.uuid4(),
        agent_thread_id=uuid.uuid4(),
        agent_run_id=uuid.uuid4(),
        command_key="legacy-owner-key-0001",
        consumed_at=datetime(2026, 8, 30, 16, 30, tzinfo=UTC),
        nutrition_catalog_version="fdc-seed-v1",
        calculation_version="per-100g-v1",
        energy_kcal=Decimal("1"),
        protein_g=Decimal("1"),
        fat_g=Decimal("1"),
        carbohydrate_g=Decimal("1"),
        created_at=NOW,
        updated_at=NOW,
        deleted_at=None,
    )
    legacy_other = MealRecord(
        id=uuid.uuid4(),
        user_id=other,
        source_run_id=uuid.uuid4(),
        agent_thread_id=uuid.uuid4(),
        agent_run_id=uuid.uuid4(),
        command_key="legacy-other-key-0001",
        consumed_at=datetime(2026, 8, 30, 16, 30, tzinfo=UTC),
        nutrition_catalog_version="fdc-seed-v1",
        calculation_version="per-100g-v1",
        energy_kcal=Decimal("1"),
        protein_g=Decimal("1"),
        fat_g=Decimal("1"),
        carbohydrate_g=Decimal("1"),
        created_at=NOW,
        updated_at=NOW,
        deleted_at=None,
    )
    owner_repository.records.extend([legacy_owner, legacy_other])
    service = _service(owner_repository)

    confirmation = service.confirm_dashboard_time_zone(
        user_id=owner, time_zone="Asia/Shanghai"
    )
    assert confirmation.dashboard_time_zone == "Asia/Shanghai"
    assert legacy_owner.consumed_local_date == date(2026, 8, 31)
    assert legacy_owner.local_date_source == "confirmed_timezone_backfill"
    assert legacy_other.consumed_local_date is None
    assert len(owner_repository.backfill_audits) == 1
    assert "historical location" not in confirmation.model_dump_json().lower()

    assert (
        service.confirm_dashboard_time_zone(user_id=owner, time_zone="Asia/Shanghai")
        == confirmation
    )


def test_dashboard_timezone_confirmation_same_key_is_idempotent_without_extra_writes() -> (
    None
):
    user_id = uuid.uuid4()
    repository = FakeMealRecordRepository(run=None, report=None)
    commits: list[bool] = []
    service = _service(repository, commits)

    first = service.confirm_dashboard_time_zone(
        user_id=user_id, time_zone="Asia/Shanghai"
    )
    second = service.confirm_dashboard_time_zone(
        user_id=user_id, time_zone="Asia/Shanghai"
    )

    assert second == first
    assert second.confirmed_at == first.confirmed_at == NOW
    assert repository.preference_add_calls == 1
    assert len(repository.backfill_audits) == 1
    assert commits == [True]


def test_dashboard_timezone_confirmation_different_key_is_generic_conflict_without_writes() -> (
    None
):
    user_id = uuid.uuid4()
    repository = FakeMealRecordRepository(run=None, report=None)
    commits: list[bool] = []
    service = _service(repository, commits)
    service.confirm_dashboard_time_zone(user_id=user_id, time_zone="Asia/Shanghai")

    with pytest.raises(DashboardTimeZoneAlreadyConfirmed) as error:
        service.confirm_dashboard_time_zone(
            user_id=user_id, time_zone="America/Los_Angeles"
        )

    assert "Asia/Shanghai" not in str(error.value)
    assert "America/Los_Angeles" not in str(error.value)
    assert repository.dashboard_time_zones[user_id].time_zone == "Asia/Shanghai"
    assert repository.preference_add_calls == 1
    assert len(repository.backfill_audits) == 1
    assert commits == [True]


@pytest.mark.parametrize(
    ("candidate", "stored", "expected_exception"),
    [
        ("Asia/Shanghai", "Asia/Shanghai", None),
        ("America/Los_Angeles", "Asia/Shanghai", DashboardTimeZoneAlreadyConfirmed),
    ],
)
def test_dashboard_timezone_confirmation_recovers_concurrent_unique_conflict_by_rereading(
    candidate: str, stored: str, expected_exception: type[Exception] | None
) -> None:
    user_id = uuid.uuid4()
    repository = FakeMealRecordRepository(run=None, report=None)
    repository.integrity_error_preference = DashboardTimezonePreference(
        user_id=user_id, time_zone=stored, confirmed_at=NOW - timedelta(minutes=1)
    )
    commits: list[bool] = []
    rollbacks: list[bool] = []
    service = _service(repository, commits, rollbacks)

    if expected_exception is None:
        confirmation = service.confirm_dashboard_time_zone(
            user_id=user_id, time_zone=candidate
        )
        assert confirmation.dashboard_time_zone == stored
        assert confirmation.confirmed_at == NOW - timedelta(minutes=1)
    else:
        with pytest.raises(expected_exception) as error:
            service.confirm_dashboard_time_zone(user_id=user_id, time_zone=candidate)
        assert stored not in str(error.value)
        assert candidate not in str(error.value)

    assert rollbacks == [True]
    assert commits == []
    assert repository.preference_add_calls == 1
    assert repository.backfill_audits == []


@pytest.mark.parametrize("invalid_time_zone", ["/invalid-timezone", "../Etc/UTC"])
def test_all_records_writes_reject_invalid_timezone_before_any_mutation(
    invalid_time_zone: str,
) -> None:
    user_id, thread_id = uuid.uuid4(), uuid.uuid4()
    repository = FakeMealRecordRepository(
        run=_run(user_id=user_id, thread_id=thread_id), report=_report()
    )
    commits: list[bool] = []
    service = _service(repository, commits)
    record = service.confirm_from_completed_run(
        user_id=user_id,
        thread_id=thread_id,
        command_key="save-key-00000001",
        consumed_at=NOW - timedelta(hours=1),
        time_zone="UTC",
    )
    preference = service.confirm_dashboard_time_zone(
        user_id=user_id, time_zone="Asia/Shanghai"
    )
    before = (
        len(repository.records),
        repository.preference_add_calls,
        len(repository.backfill_audits),
        list(commits),
    )

    with pytest.raises(InvalidTimeZone):
        service.confirm_from_completed_run(
            user_id=user_id,
            thread_id=thread_id,
            command_key="save-key-00000002",
            consumed_at=NOW - timedelta(hours=1),
            time_zone=invalid_time_zone,
        )
    with pytest.raises(InvalidTimeZone):
        service.update_record(
            record_id=record.id,
            user_id=user_id,
            consumed_at=NOW - timedelta(days=1),
            time_zone=invalid_time_zone,
        )
    with pytest.raises(InvalidTimeZone):
        service.confirm_dashboard_time_zone(
            user_id=user_id, time_zone=invalid_time_zone
        )

    assert (
        len(repository.records),
        repository.preference_add_calls,
        len(repository.backfill_audits),
        commits,
    ) == before
    assert (
        repository.dashboard_time_zones[user_id].time_zone
        == preference.dashboard_time_zone
    )


@pytest.mark.parametrize("slot", ["breakfast", "lunch", "dinner", "snack", None])
def test_meal_slot_saved_explicitly_and_preserved_when_only_time_changes(slot) -> None:
    owner, thread = uuid.uuid4(), uuid.uuid4()
    repo = FakeMealRecordRepository(
        run=_run(user_id=owner, thread_id=thread), report=_report()
    )
    service = _service(repo)
    record = service.confirm_from_completed_run(
        user_id=owner,
        thread_id=thread,
        command_key="meal-slot-save-key",
        consumed_at=NOW - timedelta(hours=12),
        time_zone="Asia/Shanghai",
        meal_slot=slot,
    )
    assert record.meal_slot == slot
    updated = service.update_record(
        record_id=record.id,
        user_id=owner,
        consumed_at=NOW - timedelta(hours=2),
        time_zone="Asia/Shanghai",
    )
    assert updated.meal_slot == slot and updated.energy_kcal == Decimal("130.0")
    changed = service.update_record(
        record_id=record.id,
        user_id=owner,
        consumed_at=NOW,
        time_zone="UTC",
        meal_slot="snack",
    )
    assert changed.meal_slot == "snack"
    cleared = service.update_record(
        record_id=record.id,
        user_id=owner,
        consumed_at=NOW,
        time_zone="UTC",
        meal_slot=None,
        update_meal_slot=True,
    )
    assert cleared.meal_slot is None
    replay = service.confirm_from_completed_run(
        user_id=owner,
        thread_id=thread,
        command_key="meal-slot-save-key",
        consumed_at=NOW,
        time_zone="UTC",
        meal_slot="dinner",
    )
    assert (
        replay.id == record.id and len(repo.records) == 1 and replay.meal_slot is None
    )


def test_invalid_slot_rejected_before_persistence() -> None:
    owner, thread = uuid.uuid4(), uuid.uuid4()
    repo = FakeMealRecordRepository(
        run=_run(user_id=owner, thread_id=thread), report=_report()
    )
    with pytest.raises(ValueError, match="invalid meal slot"):
        _service(repo).confirm_from_completed_run(
            user_id=owner,
            thread_id=thread,
            command_key="meal-slot-save-key",
            consumed_at=NOW,
            time_zone="UTC",
            meal_slot="brunch",
        )
    assert repo.records == []
