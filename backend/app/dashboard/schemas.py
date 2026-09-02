"""Strict public dashboard projections; source records and planning profiles stay private."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.dashboard.ports import PlanningTargetEligibility


class DashboardNutritionTotals(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    energy_kcal: Decimal = Field(ge=0)
    protein_g: Decimal = Field(ge=0)
    fat_g: Decimal = Field(ge=0)
    carbohydrate_g: Decimal = Field(ge=0)

    @classmethod
    def empty(cls) -> "DashboardNutritionTotals":
        return cls(energy_kcal=Decimal("0"), protein_g=Decimal("0"), fat_g=Decimal("0"), carbohydrate_g=Decimal("0"))


class DashboardDaySummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    consumed_local_date: date
    totals: DashboardNutritionTotals
    meal_count: int = Field(ge=0)


class DashboardHistoryItem(BaseModel):
    """Minimal immutable meal fact for history; no source text, image, or Agent metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    consumed_at: datetime
    totals: DashboardNutritionTotals


class DashboardHistoryGroup(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    consumed_local_date: date
    totals: DashboardNutritionTotals
    meal_count: int = Field(ge=0)
    items: tuple[DashboardHistoryItem, ...]


class DashboardOverview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    today: DashboardDaySummary
    week: tuple[DashboardDaySummary, ...] = Field(min_length=7, max_length=7)
    target_eligibility: PlanningTargetEligibility


class DashboardHistoryPage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    groups: tuple[DashboardHistoryGroup, ...]
    next_cursor: str | None = None


class DashboardHistoryRecord(Protocol):
    @property
    def consumed_local_date(self) -> date: ...

    @property
    def consumed_at(self) -> datetime: ...

    @property
    def id(self) -> uuid.UUID: ...

    @property
    def energy_kcal(self) -> Decimal: ...

    @property
    def protein_g(self) -> Decimal: ...

    @property
    def fat_g(self) -> Decimal: ...

    @property
    def carbohydrate_g(self) -> Decimal: ...


class DashboardHistoryCursor(BaseModel):
    """Private decoded keyset position; only the signed opaque string crosses HTTP."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    consumed_local_date: date
    consumed_at: datetime
    record_id: uuid.UUID

    @classmethod
    def from_record(cls, record: DashboardHistoryRecord) -> "DashboardHistoryCursor":
        return cls(
            consumed_local_date=record.consumed_local_date,
            consumed_at=record.consumed_at,
            record_id=record.id,
        )
