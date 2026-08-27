"""Public admin API contracts, separate from SQLAlchemy audit state."""

from typing import Literal

from pydantic import BaseModel


class AdminProbeResponse(BaseModel):
    """Minimal backend-only proof that database RBAC granted access."""

    status: Literal["ADMIN_ACCESS_GRANTED"] = "ADMIN_ACCESS_GRANTED"
