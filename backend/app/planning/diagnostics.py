"""Count-only planning diagnostics; never accept identity, food text or target values."""

from __future__ import annotations

import logging
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.planning.schemas import MealSlot, REQUIRED_MEAL_SLOTS

logger = logging.getLogger(__name__)


def configure_planning_diagnostics() -> None:
    """Enable the dedicated safe log without changing application-wide log levels."""
    logger.setLevel(logging.INFO)
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)


class ScanStop(StrEnum):
    EXHAUSTED = "exhausted"
    COUNT = "count_budget"
    TIME = "time_budget"


class SlotDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    pages: int = Field(default=0, ge=0)
    fetched: int = Field(default=0, ge=0)
    scanned: int = Field(default=0, ge=0)
    excluded: int = Field(default=0, ge=0)
    unavailable: int = Field(default=0, ge=0)
    filtered: int = Field(default=0, ge=0)
    nutrition_calls: int = Field(default=0, ge=0)
    eligible: int = Field(default=0, ge=0)
    components: int = Field(default=0, ge=0)
    bundle_attempts: int = Field(default=0, ge=0)
    bundles: int = Field(default=0, ge=0)
    adapted_components: int = Field(default=0, ge=0)
    adapted_bundles: int = Field(default=0, ge=0)
    bundle_stop: ScanStop | None = None
    shortlisted: int = Field(default=0, ge=0)
    stop: ScanStop | None = None
    elapsed_ms: int = Field(default=0, ge=0)


class SearchDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    slots: dict[MealSlot, SlotDiagnostics] = Field(default_factory=lambda: {
        slot: SlotDiagnostics() for slot in REQUIRED_MEAL_SLOTS
    })
    combinations: int = Field(default=0, ge=0)
    duplicate_combinations: int = Field(default=0, ge=0)
    validation_pass: int = Field(default=0, ge=0)
    validation_relax: int = Field(default=0, ge=0)
    validation_rejected: int = Field(default=0, ge=0)
    combination_stop: ScanStop | None = None
    combination_elapsed_ms: int = Field(default=0, ge=0)
    elapsed_ms: int = Field(default=0, ge=0)

    def emit(self, *, action: str, reason: str | None, policy: str) -> None:
        # The payload is deliberately assembled from a closed schema, never from
        # a command, exception, meal, preference, provider response or ORM object.
        logger.info("planning_search policy=%s action=%s reason=%s metrics=%s", policy, action, reason or "none", self.model_dump_json())
