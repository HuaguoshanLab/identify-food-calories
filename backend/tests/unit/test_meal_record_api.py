"""HTTP contract tests for meal-record routes without a database runtime."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.auth.api import get_authenticated_principal
from app.agent.graph import NoopAgentRuntimeFactory
from app.main import create_app
from app.records.api import get_meal_record_service
from app.records.models import MealRecord, MealRecordItem
from app.records.service import DashboardTimeZoneAlreadyConfirmed, InvalidTimeZone, MealRecordUnavailable


NOW = datetime(2026, 8, 31, 8, 0, tzinfo=UTC)


def _record(*, user_id: uuid.UUID) -> MealRecord:
    return MealRecord(
        id=uuid.uuid4(), user_id=user_id, source_run_id=uuid.uuid4(), agent_thread_id=uuid.uuid4(), agent_run_id=uuid.uuid4(),
        command_key="save-key-00000001", consumed_at=NOW, nutrition_catalog_version="fdc-seed-v1", calculation_version="per-100g-v1",
        energy_kcal=Decimal("130"), protein_g=Decimal("2.4"), fat_g=Decimal("0.3"), carbohydrate_g=Decimal("28.2"),
        created_at=NOW, updated_at=NOW, deleted_at=None,
        items=[MealRecordItem(id=uuid.uuid4(), user_id=user_id, position=0, display_name="米饭", food_reference="food-1", grams=Decimal("100"), energy_kcal=Decimal("130"), protein_g=Decimal("2.4"), fat_g=Decimal("0.3"), carbohydrate_g=Decimal("28.2"), is_estimated=False, created_at=NOW, updated_at=NOW, deleted_at=None)],
    )


class StubMealRecordService:
    def __init__(self, record: MealRecord) -> None:
        self.record = record
        self.confirm_calls: list[tuple[uuid.UUID, uuid.UUID, str]] = []

    def confirm_from_completed_run(self, *, user_id: uuid.UUID, thread_id: uuid.UUID, command_key: str, consumed_at: datetime | None, time_zone: str, meal_slot: str | None = None, update_meal_slot: bool = False) -> MealRecord:
        if time_zone in {"/invalid-timezone", "../Etc/UTC"}:
            raise InvalidTimeZone()
        self.confirm_calls.append((user_id, thread_id, command_key))
        return self.record

    def list_records(self, *, user_id: uuid.UUID) -> list[MealRecord]:
        return [self.record] if user_id == self.record.user_id else []

    def get_record(self, *, record_id: uuid.UUID, user_id: uuid.UUID) -> MealRecord:
        if record_id != self.record.id or user_id != self.record.user_id:
            raise MealRecordUnavailable()
        return self.record

    def update_record(self, *, record_id: uuid.UUID, user_id: uuid.UUID, consumed_at: datetime, time_zone: str, meal_slot: str | None = None, update_meal_slot: bool = False) -> MealRecord:
        if time_zone in {"/invalid-timezone", "../Etc/UTC"}:
            raise InvalidTimeZone()
        return self.get_record(record_id=record_id, user_id=user_id)

    def confirm_dashboard_time_zone(self, *, user_id: uuid.UUID, time_zone: str):
        if time_zone in {"Mars/Olympus_Mons", "/invalid-timezone", "../Etc/UTC"}:
            raise InvalidTimeZone()
        if time_zone == "Etc/GMT":
            raise DashboardTimeZoneAlreadyConfirmed()
        return type("Confirmation", (), {"dashboard_time_zone": time_zone, "confirmed_at": NOW})()

    def delete_record(self, *, record_id: uuid.UUID, user_id: uuid.UUID) -> None:
        self.get_record(record_id=record_id, user_id=user_id)


def _client(*, principal: uuid.UUID, service: StubMealRecordService) -> TestClient:
    app = create_app(runtime_factory=NoopAgentRuntimeFactory())
    app.dependency_overrides[get_authenticated_principal] = lambda: principal
    app.dependency_overrides[get_meal_record_service] = lambda: service
    return TestClient(app)


def test_meal_record_openapi_and_schema_reject_client_nutrition_values() -> None:
    user_id = uuid.uuid4()
    service = StubMealRecordService(_record(user_id=user_id))
    with _client(principal=user_id, service=service) as client:
        openapi = client.app.openapi()
        assert set(openapi["paths"]["/api/v1/meal-records"]) == {"get", "post"}
        assert set(openapi["paths"]["/api/v1/meal-records/{record_id}"]) == {"get", "patch", "delete"}
        response = client.post("/api/v1/meal-records", json={"thread_id": str(uuid.uuid4()), "command_key": "save-key-00000001", "energy_kcal": "9999"})
    assert response.status_code == 422
    assert service.confirm_calls == []


def test_authenticated_owner_can_list_and_confirm_without_exposing_agent_run_ids() -> None:
    user_id = uuid.uuid4()
    record = _record(user_id=user_id)
    service = StubMealRecordService(record)
    with _client(principal=user_id, service=service) as client:
        listed = client.get("/api/v1/meal-records")
        confirmed = client.post("/api/v1/meal-records", json={"thread_id": str(uuid.uuid4()), "command_key": "save-key-00000001", "time_zone": "Asia/Shanghai"})
    assert listed.status_code == 200 and listed.json()[0]["id"] == str(record.id)
    assert confirmed.status_code == 201 and "agent_run_id" not in confirmed.json() and "source_run_id" not in confirmed.json()
    assert service.confirm_calls[0][0] == user_id


def test_time_zone_contract_requires_iana_input_and_exposes_only_current_statistical_basis() -> None:
    user_id = uuid.uuid4()
    service = StubMealRecordService(_record(user_id=user_id))
    with _client(principal=user_id, service=service) as client:
        invalid = client.post("/api/v1/meal-records/dashboard-time-zone-confirmations", json={"time_zone": "Mars/Olympus_Mons"})
        confirmed = client.post("/api/v1/meal-records/dashboard-time-zone-confirmations", json={"time_zone": "America/Los_Angeles"})
        saved_without_zone = client.post("/api/v1/meal-records", json={"thread_id": str(uuid.uuid4()), "command_key": "save-key-00000002"})
    assert invalid.status_code == 400
    assert confirmed.status_code == 200
    assert confirmed.json()["dashboard_time_zone"] == "America/Los_Angeles"
    assert "historical_location" not in confirmed.json()
    assert saved_without_zone.status_code == 422


def test_dashboard_timezone_conflict_is_generic_and_does_not_disclose_stored_basis() -> None:
    user_id = uuid.uuid4()
    service = StubMealRecordService(_record(user_id=user_id))
    with _client(principal=user_id, service=service) as client:
        response = client.post(
            "/api/v1/meal-records/dashboard-time-zone-confirmations", json={"time_zone": "Etc/GMT"}
        )

    assert response.status_code == 409
    body = response.text.lower()
    assert "etc/gmt" not in body
    assert "preference" not in body
    assert "confirmed_at" not in body


@pytest.mark.parametrize("invalid_time_zone", ["/invalid-timezone", "../Etc/UTC"])
def test_records_write_routes_map_invalid_timezone_to_safe_400_without_details(invalid_time_zone: str) -> None:
    user_id = uuid.uuid4()
    record = _record(user_id=user_id)
    service = StubMealRecordService(record)
    with _client(principal=user_id, service=service) as client:
        create = client.post(
            "/api/v1/meal-records",
            json={
                "thread_id": str(uuid.uuid4()),
                "command_key": "save-key-00000001",
                "time_zone": invalid_time_zone,
            },
        )
        edit = client.patch(
            f"/api/v1/meal-records/{record.id}",
            json={"consumed_at": NOW.isoformat(), "time_zone": invalid_time_zone},
        )
        confirmation = client.post(
            "/api/v1/meal-records/dashboard-time-zone-confirmations",
            json={"time_zone": invalid_time_zone},
        )

    for response in (create, edit, confirmation):
        assert response.status_code == 400
        body = response.text.lower()
        assert "traceback" not in body
        assert "exception" not in body
        assert "provider" not in body
        assert "token" not in body
        assert "preference" not in body
        assert "record" not in body
    assert service.confirm_calls == []


def test_foreign_record_uuid_has_the_same_not_found_result_for_get_patch_and_delete() -> None:
    owner, other = uuid.uuid4(), uuid.uuid4()
    record = _record(user_id=owner)
    service = StubMealRecordService(record)
    with _client(principal=other, service=service) as client:
        assert client.get(f"/api/v1/meal-records/{record.id}").status_code == 404
        assert client.patch(f"/api/v1/meal-records/{record.id}", json={"consumed_at": NOW.isoformat(), "time_zone": "UTC"}).status_code == 404
        assert client.delete(f"/api/v1/meal-records/{record.id}").status_code == 404


@pytest.mark.parametrize("slot", ["brunch", "早餐", "", 1, ["breakfast"]])
def test_invalid_meal_slot_rejected_by_both_write_contracts(slot) -> None:
    owner = uuid.uuid4()
    record = _record(user_id=owner)
    service = StubMealRecordService(record)
    with _client(principal=owner, service=service) as client:
        response = client.post("/api/v1/meal-records", json={"thread_id": str(uuid.uuid4()), "command_key": "meal-slot-save-key", "time_zone": "UTC", "meal_slot": slot})
        assert response.status_code == 422
        response = client.patch(f"/api/v1/meal-records/{record.id}", json={"consumed_at": NOW.isoformat(), "time_zone": "UTC", "meal_slot": slot})
        assert response.status_code == 422
    assert service.confirm_calls == []
