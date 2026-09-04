"""Consumer-owned, minimal completion-target contract for the dashboard."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel, ConfigDict, model_validator

from app.planning.schemas import DailyTarget


@dataclass(frozen=True)
class DashboardTimezone:
    """The records-owned, explicitly confirmed statistical basis for one user."""

    time_zone: str


class DashboardTimezoneReadPort(Protocol):
    """Read only the confirmed statistical basis; dashboard never writes it."""

    def get_dashboard_timezone_for_user(self, *, user_id: uuid.UUID) -> DashboardTimezone | None: ...


class CompletionTargetProjection(Protocol):
    """Attributes the dashboard may transform, without importing the planning ORM."""

    energy_kcal_lower: Decimal
    energy_kcal_upper: Decimal
    carbohydrate_g_lower: Decimal
    carbohydrate_g_upper: Decimal
    protein_g_lower: Decimal
    protein_g_upper: Decimal
    fat_g_lower: Decimal
    fat_g_upper: Decimal
    target_version: str


class PlanningTargetEligibility(BaseModel):
    """Target data is structurally impossible unless a validated completion permits it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    eligible: bool
    target: DailyTarget | None = None
    target_version: str | None = None

    @model_validator(mode="after")
    def keeps_unavailable_targets_empty(self) -> "PlanningTargetEligibility":
        if self.eligible != (self.target is not None and self.target_version is not None):
            raise ValueError("target data must exist exactly when completion eligibility is true")
        return self

    @classmethod
    def unavailable(cls) -> "PlanningTargetEligibility":
        return cls(eligible=False)

    @classmethod
    def from_projection(cls, projection: CompletionTargetProjection) -> "PlanningTargetEligibility":
        from app.planning.schemas import TargetRange

        return cls(
            eligible=True,
            target=DailyTarget(
                energy_kcal=TargetRange(lower=projection.energy_kcal_lower, upper=projection.energy_kcal_upper),
                carbohydrate_g=TargetRange(lower=projection.carbohydrate_g_lower, upper=projection.carbohydrate_g_upper),
                protein_g=TargetRange(lower=projection.protein_g_lower, upper=projection.protein_g_upper),
                fat_g=TargetRange(lower=projection.fat_g_lower, upper=projection.fat_g_upper),
            ),
            target_version=projection.target_version,
        )


class PlanningCompletionTargetPort(Protocol):
    """The dashboard learns nothing except current target eligibility and safe ranges."""

    def get_dashboard_target_eligibility(self, *, user_id: uuid.UUID) -> PlanningTargetEligibility: ...
