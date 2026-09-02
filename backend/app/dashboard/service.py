"""Dashboard read use cases over snapshot facts and a narrow completion-target port."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from collections import defaultdict
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Protocol

from app.dashboard.ports import PlanningCompletionTargetPort
from app.dashboard.schemas import (
    DashboardDaySummary,
    DashboardHistoryCursor,
    DashboardHistoryGroup,
    DashboardHistoryItem,
    DashboardHistoryPage,
    DashboardHistoryRecord,
    DashboardNutritionTotals,
    DashboardOverview,
)


class DashboardAggregate(Protocol):
    @property
    def consumed_local_date(self) -> date: ...

    @property
    def totals(self) -> DashboardNutritionTotals: ...

    @property
    def meal_count(self) -> int: ...


class DashboardRepository(Protocol):
    def get_daily_aggregates(self, *, user_id: uuid.UUID, start_date: date, end_date: date) -> Sequence[DashboardAggregate]: ...
    def get_history_page(self, *, user_id: uuid.UUID, cursor: DashboardHistoryCursor | None, limit: int) -> Sequence[DashboardHistoryRecord]: ...


class InvalidDashboardCursor(ValueError):
    """Raised before a malformed or modified cursor can reach the repository."""


class DashboardCursorCodec:
    """Signs keyset positions so clients cannot alter dates, timestamps, or UUID ties."""

    def __init__(self, secret: str) -> None:
        self._secret = secret.encode("utf-8")

    def encode(self, cursor: DashboardHistoryCursor) -> str:
        payload = json.dumps(cursor.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(self._secret, payload, hashlib.sha256).digest()
        return _b64encode(payload) + "." + _b64encode(signature)

    def decode(self, value: str) -> DashboardHistoryCursor:
        try:
            encoded_payload, encoded_signature = value.split(".", 1)
            payload, signature = _b64decode(encoded_payload), _b64decode(encoded_signature)
            expected = hmac.new(self._secret, payload, hashlib.sha256).digest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError("signature mismatch")
            return DashboardHistoryCursor.model_validate_json(payload)
        except (TypeError, ValueError) as error:
            raise InvalidDashboardCursor("dashboard cursor is invalid") from error


class DashboardService:
    def __init__(
        self,
        *,
        repository: DashboardRepository,
        target_port: PlanningCompletionTargetPort,
        now: Callable[[], datetime] | None = None,
        cursor_secret: str = "dashboard-test-cursor-secret",
    ) -> None:
        self._repository = repository
        self._target_port = target_port
        self._now = now or (lambda: datetime.now(UTC))
        self._cursor_codec = DashboardCursorCodec(cursor_secret)

    def get_overview(self, *, user_id: uuid.UUID, week_start: date | None = None) -> DashboardOverview:
        today = self._now().date()
        start = week_start or today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        aggregates = {
            aggregate.consumed_local_date: aggregate
            for aggregate in self._repository.get_daily_aggregates(user_id=user_id, start_date=start, end_date=end)
        }
        week = tuple(self._day_summary(day=current_day, aggregate=aggregates.get(current_day)) for current_day in _days(start, end))
        today_summary = self._day_summary(day=today, aggregate=aggregates.get(today))
        return DashboardOverview(today=today_summary, week=week, target_eligibility=self._target_port.get_dashboard_target_eligibility(user_id=user_id))

    def get_history(self, *, user_id: uuid.UUID, cursor: str | None, limit: int) -> DashboardHistoryPage:
        decoded = self._cursor_codec.decode(cursor) if cursor is not None else None
        rows = self._repository.get_history_page(user_id=user_id, cursor=decoded, limit=limit + 1)
        page_rows, has_more = rows[:limit], len(rows) > limit
        grouped: dict[date, list[DashboardHistoryRecord]] = defaultdict(list)
        for record in page_rows:
            grouped[record.consumed_local_date].append(record)
        groups = tuple(self._history_group(day=day, records=records) for day, records in grouped.items())
        next_cursor = self._cursor_codec.encode(DashboardHistoryCursor.from_record(page_rows[-1])) if has_more else None
        return DashboardHistoryPage(groups=groups, next_cursor=next_cursor)

    @staticmethod
    def _day_summary(*, day: date, aggregate: DashboardAggregate | None) -> DashboardDaySummary:
        if aggregate is None:
            return DashboardDaySummary(consumed_local_date=day, totals=DashboardNutritionTotals.empty(), meal_count=0)
        return DashboardDaySummary(consumed_local_date=day, totals=aggregate.totals, meal_count=aggregate.meal_count)

    @staticmethod
    def _history_group(*, day: date, records: list[DashboardHistoryRecord]) -> DashboardHistoryGroup:
        totals = DashboardNutritionTotals(
            energy_kcal=sum((record.energy_kcal for record in records), start=Decimal("0")),
            protein_g=sum((record.protein_g for record in records), start=Decimal("0")),
            fat_g=sum((record.fat_g for record in records), start=Decimal("0")),
            carbohydrate_g=sum((record.carbohydrate_g for record in records), start=Decimal("0")),
        )
        return DashboardHistoryGroup(
            consumed_local_date=day,
            totals=totals,
            meal_count=len(records),
            items=tuple(
                DashboardHistoryItem(
                    id=record.id,
                    consumed_at=record.consumed_at,
                    totals=DashboardNutritionTotals(
                        energy_kcal=record.energy_kcal, protein_g=record.protein_g,
                        fat_g=record.fat_g, carbohydrate_g=record.carbohydrate_g,
                    ),
                )
                for record in records
            ),
        )


def _days(start: date, end: date) -> tuple[date, ...]:
    return tuple(start + timedelta(days=index) for index in range((end - start).days + 1))


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
