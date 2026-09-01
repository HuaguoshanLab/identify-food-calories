"""Minimal, owner-bound persisted inputs for deterministic diet planning."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.auth.models import Base


class PlanningProfile(Base):
    """One active snapshot per user; preferences remain exclusively in the memory ledger."""

    __tablename__ = "planning_profiles"
    __table_args__ = (
        CheckConstraint("height_cm >= 100 AND height_cm <= 250", name="ck_planning_profiles_height_range"),
        CheckConstraint("weight_kg >= 20 AND weight_kg <= 350", name="ck_planning_profiles_weight_range"),
        CheckConstraint("age_years >= 1 AND age_years <= 130", name="ck_planning_profiles_age_range"),
        CheckConstraint("formula_variant IN ('mifflin_st_jeor_male', 'mifflin_st_jeor_female')", name="ck_planning_profiles_formula_variant"),
        CheckConstraint("activity_level IN ('sedentary', 'light', 'moderate', 'high', 'very_high')", name="ck_planning_profiles_activity_level"),
        CheckConstraint("goal IN ('maintain', 'loss', 'gain')", name="ck_planning_profiles_goal"),
        CheckConstraint("goal_speed IN ('maintain', 'gradual_loss', 'gradual_gain')", name="ck_planning_profiles_goal_speed"),
        Index("uq_planning_profiles_active_user", "user_id", unique=True, postgresql_where=text("deleted_at IS NULL")),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    height_cm: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    age_years: Mapped[int] = mapped_column(Integer, nullable=False)
    formula_variant: Mapped[str] = mapped_column(String(48), nullable=False)
    activity_level: Mapped[str] = mapped_column(String(24), nullable=False)
    goal: Mapped[str] = mapped_column(String(16), nullable=False)
    goal_speed: Mapped[str] = mapped_column(String(24), nullable=False)
    target_policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    formula_version: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
