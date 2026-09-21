"""Application rules for explicit meal saving and tenant-bound snapshot management."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.exc import IntegrityError

from app.records.models import (
    DashboardTimezoneBackfillAudit,
    DashboardTimezonePreference,
    MealRecord,
    MealRecordItem,
)
from app.records.ports import MealRecordRepository
from app.records.schemas import DashboardTimezoneConfirmationResponse
from app.nutrition.schemas import NutritionAction, NutritionCalculationInput, NutritionCalculationResult


class RecordNutritionCalculator(Protocol):
    def calculate_nutrition(self, request: NutritionCalculationInput) -> NutritionCalculationResult: ...


class MealRecordUnavailable(LookupError):
    """Uniform missing/foreign/deleted record result."""


class MealRecordConfirmationUnavailable(ValueError):
    """The chosen thread has no complete, fully calculable report."""


class MealRecordCommandConflict(ValueError):
    """A save idempotency key cannot be rebound to another completed report."""


class ConsumedAtInvalid(ValueError):
    """Future meal times are forbidden because they would fabricate history."""


class InvalidTimeZone(ValueError):
    """Timezone input must be a named IANA zone that zoneinfo can resolve."""


class DashboardTimeZoneAlreadyConfirmed(ValueError):
    """Legacy attribution is intentionally a one-time user-confirmed operation."""


class MealRecordService:
    """Builds snapshots only from persisted deterministic Agent reports, never client totals."""

    _MIXED_CATALOG_SNAPSHOT_VERSION = "multiple-catalogs-v1"

    def __init__(
        self,
        *,
        repository: MealRecordRepository,
        now: Callable[[], datetime] | None = None,
        commit: Callable[[], None] | None = None,
        rollback: Callable[[], None] | None = None,
        nutrition_calculator: RecordNutritionCalculator | None = None,
    ) -> None:
        self._repository = repository
        self._now = now or (lambda: datetime.now(UTC))
        self._commit = commit or (lambda: None)
        self._rollback = rollback or (lambda: None)
        self._nutrition_calculator = nutrition_calculator

    def confirm_from_completed_run(
        self,
        *,
        user_id: uuid.UUID,
        thread_id: uuid.UUID,
        command_key: str,
        consumed_at: datetime | None,
        time_zone: str,
        meal_slot: str | None = None,
    ) -> MealRecord:
        self._validate_meal_slot(meal_slot)
        now = self._now()
        when = consumed_at or now
        self._validate_consumed_at(when, now)
        zone = self._validated_time_zone(time_zone)
        by_command = self._repository.get_record_for_command_for_user(
            command_key=command_key, user_id=user_id, include_deleted=True
        )
        run = self._repository.get_completed_run_for_thread_for_user(
            thread_id=thread_id, user_id=user_id, for_update=True
        )
        if run is None:
            raise MealRecordConfirmationUnavailable("completed report is unavailable")
        if by_command is not None:
            if by_command.source_run_id != run.id:
                raise MealRecordCommandConflict("save idempotency key payload mismatch")
            return by_command
        existing = self._repository.get_record_for_source_run_for_user(
            source_run_id=run.id, user_id=user_id, include_deleted=True
        )
        if existing is not None:
            return existing
        event = self._repository.get_completed_report_for_run_for_user(
            run_id=run.id, user_id=user_id
        )
        report = event.payload.get("report") if event is not None else None
        snapshot = self._validated_snapshot(report)
        record = MealRecord(
            id=uuid.uuid4(),
            user_id=user_id,
            source_run_id=run.id,
            agent_thread_id=thread_id,
            agent_run_id=run.id,
            command_key=command_key,
            meal_slot=meal_slot,
            consumed_at=when,
            consumed_time_zone=zone.key,
            consumed_local_date=self._local_date(when, zone),
            local_date_source="submitted_time_zone",
            nutrition_catalog_version=snapshot["catalog_version"],
            calculation_version=snapshot["calculation_version"],
            energy_kcal=snapshot["energy_kcal"],
            protein_g=snapshot["protein_g"],
            fat_g=snapshot["fat_g"],
            carbohydrate_g=snapshot["carbohydrate_g"],
            created_at=now,
            updated_at=now,
            deleted_at=None,
            items=[
                MealRecordItem(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    position=index,
                    display_name=item["name"],
                    food_reference=item["food_reference"],
                    nutrition_catalog_version=item["catalog_version"],
                    grams=item["grams"],
                    energy_kcal=item["energy_kcal"],
                    protein_g=item["protein_g"],
                    fat_g=item["fat_g"],
                    carbohydrate_g=item["carbohydrate_g"],
                    is_estimated=item["is_estimated"],
                    created_at=now,
                    updated_at=now,
                    deleted_at=None,
                )
                for index, item in enumerate(snapshot["items"])
            ],
        )
        try:
            saved = self._repository.add_record(record)
            self._commit()
            return saved
        except Exception:
            self._rollback()
            raise

    def list_records(self, *, user_id: uuid.UUID) -> list[MealRecord]:
        return self._repository.list_records_for_user(user_id=user_id)

    def get_record(self, *, record_id: uuid.UUID, user_id: uuid.UUID) -> MealRecord:
        record = self._repository.get_record_for_user(
            record_id=record_id, user_id=user_id
        )
        if record is None:
            raise MealRecordUnavailable("meal record is unavailable")
        return record

    def update_record(
        self,
        *,
        record_id: uuid.UUID,
        user_id: uuid.UUID,
        consumed_at: datetime,
        time_zone: str,
        meal_slot: str | None = None,
        update_meal_slot: bool = False,
        item_corrections: tuple[tuple[uuid.UUID, Decimal], ...] | None = None,
    ) -> MealRecord:
        now = self._now()
        self._validate_meal_slot(meal_slot)
        self._validate_consumed_at(consumed_at, now)
        zone = self._validated_time_zone(time_zone)
        record = self._repository.get_record_for_user(
            record_id=record_id, user_id=user_id, for_update=True
        )
        if record is None:
            raise MealRecordUnavailable("meal record is unavailable")
        try:
            # Changing occurrence time must not silently recalculate an historical nutrition snapshot.
            if update_meal_slot or meal_slot is not None:
                record.meal_slot = meal_slot
            record.consumed_at = consumed_at
            record.consumed_time_zone = zone.key
            record.consumed_local_date = self._local_date(consumed_at, zone)
            record.local_date_source = "submitted_time_zone"
            if item_corrections is not None:
                self._apply_item_corrections(record, item_corrections, now)
            record.updated_at = now
            self._commit()
            return record
        except Exception:
            self._rollback()
            raise

    def _apply_item_corrections(
        self,
        record: MealRecord,
        corrections: tuple[tuple[uuid.UUID, Decimal], ...],
        now: datetime,
    ) -> None:
        if self._nutrition_calculator is None:
            raise MealRecordConfirmationUnavailable("nutrition calculator is unavailable")
        if len({item_id for item_id, _grams in corrections}) != len(corrections):
            raise MealRecordConfirmationUnavailable("duplicate corrected item")
        by_id = {item.id: item for item in record.items if item.deleted_at is None}
        if set(by_id) != {item_id for item_id, _grams in corrections}:
            raise MealRecordConfirmationUnavailable("correction must include every active item")
        for item_id, grams in corrections:
            item = by_id[item_id]
            try:
                food_id = uuid.UUID(item.food_reference)
            except ValueError:
                raise MealRecordConfirmationUnavailable("record item cannot be recalculated") from None
            result = self._nutrition_calculator.calculate_nutrition(
                NutritionCalculationInput(
                    food_id=food_id,
                    catalog_version=item.nutrition_catalog_version,
                    grams=grams,
                )
            )
            if result.action is not NutritionAction.PASS or result.food is None or result.nutrients is None:
                raise MealRecordConfirmationUnavailable("record item is no longer calculable")
            item.display_name = result.food.canonical_name
            item.grams = grams
            item.energy_kcal = result.nutrients.energy_kcal
            item.protein_g = result.nutrients.protein_g
            item.fat_g = result.nutrients.fat_g
            item.carbohydrate_g = result.nutrients.carbohydrate_g
            item.is_estimated = False
            item.updated_at = now
        for metric in ("energy_kcal", "protein_g", "fat_g", "carbohydrate_g"):
            setattr(record, metric, sum((getattr(item, metric) for item in by_id.values()), Decimal(0)))

    def confirm_dashboard_time_zone(
        self, *, user_id: uuid.UUID, time_zone: str
    ) -> DashboardTimezoneConfirmationResponse:
        """Backfill only after an explicit current statistical-basis confirmation."""

        now = self._now()
        zone = self._validated_time_zone(time_zone)
        existing_preference = (
            self._repository.get_dashboard_time_zone_preference_for_user(
                user_id=user_id, for_update=True
            )
        )
        if existing_preference is not None:
            return self._confirmed_dashboard_time_zone_or_conflict(
                preference=existing_preference, candidate_time_zone=zone
            )
        legacy_records = self._repository.list_records_without_local_date_for_user(
            user_id=user_id
        )
        try:
            self._repository.add_dashboard_time_zone_preference(
                DashboardTimezonePreference(
                    user_id=user_id, time_zone=zone.key, confirmed_at=now
                )
            )
            for record in legacy_records:
                record.consumed_time_zone = zone.key
                record.consumed_local_date = self._local_date(record.consumed_at, zone)
                record.local_date_source = "confirmed_timezone_backfill"
                record.updated_at = now
            self._repository.add_timezone_backfill_audit(
                DashboardTimezoneBackfillAudit(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    confirmed_time_zone=zone.key,
                    records_backfilled=len(legacy_records),
                    confirmed_at=now,
                )
            )
            self._commit()
            return DashboardTimezoneConfirmationResponse(
                dashboard_time_zone=zone.key, confirmed_at=now
            )
        except IntegrityError as error:
            # The unique preference/audit constraints are the final one-time-confirmation guard
            # when concurrent requests both observed no row before acquiring their transaction locks.
            self._rollback()
            existing_preference = (
                self._repository.get_dashboard_time_zone_preference_for_user(
                    user_id=user_id, for_update=True
                )
            )
            if existing_preference is not None:
                return self._confirmed_dashboard_time_zone_or_conflict(
                    preference=existing_preference, candidate_time_zone=zone
                )
            raise DashboardTimeZoneAlreadyConfirmed(
                "dashboard timezone has already been confirmed"
            ) from error
        except Exception:
            self._rollback()
            raise

    def delete_record(self, *, record_id: uuid.UUID, user_id: uuid.UUID) -> None:
        record = self._repository.get_record_for_user(
            record_id=record_id, user_id=user_id, for_update=True
        )
        if record is None:
            raise MealRecordUnavailable("meal record is unavailable")
        now = self._now()
        try:
            record.deleted_at = now
            record.updated_at = now
            for item in record.items:
                item.deleted_at = now
                item.updated_at = now
            self._commit()
        except Exception:
            self._rollback()
            raise

    @staticmethod
    def _validate_meal_slot(meal_slot: str | None) -> None:
        if meal_slot not in (None, "breakfast", "lunch", "dinner", "snack"):
            raise ValueError("invalid meal slot")

    @staticmethod
    def _validate_consumed_at(consumed_at: datetime, now: datetime) -> None:
        if consumed_at.tzinfo is None or consumed_at > now:
            raise ConsumedAtInvalid(
                "consumed_at must be a past or current aware datetime"
            )

    @staticmethod
    def _validated_time_zone(time_zone: str) -> ZoneInfo:
        try:
            return ZoneInfo(time_zone)
        except (TypeError, ValueError, ZoneInfoNotFoundError) as error:
            raise InvalidTimeZone("time_zone must be a valid IANA timezone") from error

    @staticmethod
    def _confirmed_dashboard_time_zone_or_conflict(
        *, preference: DashboardTimezonePreference, candidate_time_zone: ZoneInfo
    ) -> DashboardTimezoneConfirmationResponse:
        """Only the identical persisted statistical basis may safely replay a confirmation."""

        if preference.time_zone != candidate_time_zone.key:
            raise DashboardTimeZoneAlreadyConfirmed(
                "dashboard timezone has already been confirmed"
            )
        return DashboardTimezoneConfirmationResponse(
            dashboard_time_zone=preference.time_zone,
            confirmed_at=preference.confirmed_at,
        )

    @staticmethod
    def _local_date(consumed_at: datetime, zone: ZoneInfo) -> date:
        return consumed_at.astimezone(zone).date()

    @staticmethod
    def _decimal(value: object, *, field: str) -> Decimal:
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError) as error:
            raise MealRecordConfirmationUnavailable(
                f"invalid completed report {field}"
            ) from error
        if not result.is_finite() or result < 0:
            raise MealRecordConfirmationUnavailable(f"invalid completed report {field}")
        return result

    @classmethod
    def _validated_snapshot(cls, report: object) -> dict[str, Any]:
        if (
            not isinstance(report, dict)
            or report.get("waiting_input")
            or report.get("is_partial")
        ):
            raise MealRecordConfirmationUnavailable("report is not complete")
        raw_items = report.get("items")
        totals = report.get("totals")
        if (
            not isinstance(raw_items, list)
            or not raw_items
            or not isinstance(totals, dict)
        ):
            raise MealRecordConfirmationUnavailable(
                "report has no complete nutrition snapshot"
            )
        items: list[dict[str, Any]] = []
        catalog_versions: set[str] = set()
        calculation_versions: set[str] = set()
        summed = {
            field: Decimal("0")
            for field in ("energy_kcal", "protein_g", "fat_g", "carbohydrate_g")
        }
        for raw in raw_items:
            if not isinstance(raw, dict):
                raise MealRecordConfirmationUnavailable("invalid report item")
            name, food_id, catalog_version, calculation_version = (
                raw.get(key)
                for key in (
                    "name",
                    "food_id",
                    "catalog_version",
                    "calculation_rule_version",
                )
            )
            if not all(
                isinstance(value, str) and value.strip()
                for value in (name, food_id, catalog_version, calculation_version)
            ):
                raise MealRecordConfirmationUnavailable(
                    "report item lacks immutable references"
                )
            grams = cls._decimal(raw.get("grams"), field="grams")
            item: dict[str, Any] = {
                "name": name,
                "food_reference": food_id,
                "catalog_version": catalog_version,
                "grams": grams,
                "is_estimated": bool(raw.get("is_estimated", False)),
            }
            if grams <= 0:
                raise MealRecordConfirmationUnavailable(
                    "invalid completed report grams"
                )
            for field in summed:
                nutrient = cls._decimal(raw.get(field), field=field)
                item[field] = nutrient
                summed[field] += nutrient
            catalog_versions.add(str(catalog_version))
            calculation_versions.add(str(calculation_version))
            items.append(item)
        if len(calculation_versions) != 1:
            raise MealRecordConfirmationUnavailable(
                "report uses incompatible nutrition versions"
            )
        for field, expected in summed.items():
            if cls._decimal(totals.get(field), field=field) != expected.quantize(
                Decimal("0.1")
            ):
                raise MealRecordConfirmationUnavailable(
                    "report totals do not match deterministic items"
                )
        return {
            "items": items,
            "catalog_version": (
                catalog_versions.pop()
                if len(catalog_versions) == 1
                else cls._MIXED_CATALOG_SNAPSHOT_VERSION
            ),
            "calculation_version": calculation_versions.pop(),
            **summed,
        }
