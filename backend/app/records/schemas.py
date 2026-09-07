"""Public DTOs for meal-record operations; agent/provider internals stay private."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


MealSlot = Literal["breakfast", "lunch", "dinner", "snack"]


class MealRecordConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thread_id: uuid.UUID
    command_key: str = Field(min_length=16, max_length=128)
    meal_slot: MealSlot | None = None
    consumed_at: datetime | None = None
    time_zone: str = Field(min_length=1, max_length=64)


class MealRecordUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meal_slot: MealSlot | None = None

    consumed_at: datetime
    time_zone: str = Field(min_length=1, max_length=64)


class DashboardTimezoneConfirmationRequest(BaseModel):
    """A statistical basis confirmation, not a reconstruction of historical whereabouts."""

    model_config = ConfigDict(extra="forbid")

    time_zone: str = Field(min_length=1, max_length=64)


class DashboardTimezoneConfirmationResponse(BaseModel):
    """Safe current-basis DTO with no claim about historical location."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    dashboard_time_zone: str
    confirmed_at: datetime


class MealRecordItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    position: int
    display_name: str
    nutrition_catalog_version: str
    grams: Decimal
    energy_kcal: Decimal
    protein_g: Decimal
    fat_g: Decimal
    carbohydrate_g: Decimal
    is_estimated: bool


class MealRecordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    meal_slot: MealSlot | None = None
    consumed_at: datetime
    consumed_time_zone: str | None
    consumed_local_date: date | None
    local_date_source: str | None
    nutrition_catalog_version: str
    calculation_version: str
    energy_kcal: Decimal
    protein_g: Decimal
    fat_g: Decimal
    carbohydrate_g: Decimal
    created_at: datetime
    updated_at: datetime
    items: list[MealRecordItemResponse]
