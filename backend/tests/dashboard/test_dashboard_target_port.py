"""RED consumer contract: dashboard receives eligibility, never profile fields."""

from __future__ import annotations

import uuid

from app.dashboard.ports import PlanningTargetEligibility


class FakePlanningTargetPort:
    def __init__(self, values: dict[uuid.UUID, PlanningTargetEligibility]) -> None:
        self._values = values

    def get_dashboard_target_eligibility(self, *, user_id: uuid.UUID) -> PlanningTargetEligibility:
        return self._values.get(user_id, PlanningTargetEligibility.unavailable())


def test_dashboard_target_port_exposes_only_eligibility_ranges_and_version() -> None:
    user_id = uuid.uuid4()
    port = FakePlanningTargetPort({})

    unavailable = port.get_dashboard_target_eligibility(user_id=user_id)

    assert unavailable.eligible is False
    assert unavailable.target is None
    assert unavailable.target_version is None
    assert set(unavailable.model_fields) == {"eligible", "target", "target_version"}
