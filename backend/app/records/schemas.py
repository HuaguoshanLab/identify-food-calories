"""Public DTOs for meal-record operations; agent/provider internals stay private."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class MealRecordConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thread_id: uuid.UUID
    command_key: str = Field(min_length=16, max_length=128)
    consumed_at: datetime | None = None


class MealRecordUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consumed_at: datetime


class MealRecordItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    position: int
    display_name: str
    grams: Decimal
    energy_kcal: Decimal
    protein_g: Decimal
    fat_g: Decimal
    carbohydrate_g: Decimal
    is_estimated: bool


class MealRecordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    consumed_at: datetime
    nutrition_catalog_version: str
    calculation_version: str
    energy_kcal: Decimal
    protein_g: Decimal
    fat_g: Decimal
    carbohydrate_g: Decimal
    created_at: datetime
    updated_at: datetime
    items: list[MealRecordItemResponse]
