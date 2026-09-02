"""Dashboard-owned persisted projections with minimal cache payloads."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.auth.models import Base


class WeeklyReviewResult(Base):
    """Replayable, safe weekly advice; never a provider transcript or facts blob."""

    __tablename__ = "weekly_review_results"
    __table_args__ = (
        CheckConstraint("status IN ('running', 'completed', 'abstained', 'outcome_unknown')", name="ck_weekly_review_results_status"),
        CheckConstraint("facts_digest ~ '^[a-f0-9]{64}$'", name="ck_weekly_review_results_facts_digest"),
        CheckConstraint("result_digest ~ '^[a-f0-9]{64}$'", name="ck_weekly_review_results_result_digest"),
        CheckConstraint("(status = 'completed' AND advice IS NOT NULL AND abstention_code IS NULL) OR (status = 'abstained' AND advice IS NULL AND abstention_code IS NOT NULL) OR (status IN ('running', 'outcome_unknown') AND advice IS NULL)", name="ck_weekly_review_results_safe_payload"),
        UniqueConstraint("user_id", "week_start", "facts_digest", "graph_version", "prompt_version", "schema_version", "runtime_config_version", name="uq_weekly_review_results_cache_key"),
        Index("ix_weekly_review_results_user_week", "user_id", "week_start"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    facts_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    graph_version: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(80), nullable=False)
    runtime_config_version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    advice: Mapped[str | None] = mapped_column(String(500))
    abstention_code: Mapped[str | None] = mapped_column(String(80))
    result_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("agent_runs.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
