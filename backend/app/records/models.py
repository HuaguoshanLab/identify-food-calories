"""Authoritative meal snapshots and auditable preference-memory metadata."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.auth.models import Base


class MealRecord(Base):
    """One user-confirmed immutable-source snapshot; edits affect only the current record."""

    __tablename__ = "meal_records"
    __table_args__ = (
        CheckConstraint("energy_kcal >= 0 AND protein_g >= 0 AND fat_g >= 0 AND carbohydrate_g >= 0", name="ck_meal_records_nonnegative_totals"),
        CheckConstraint("consumed_at <= updated_at", name="ck_meal_records_consumed_before_update"),
        UniqueConstraint("user_id", "source_run_id", name="uq_meal_records_user_source_run"),
        UniqueConstraint("user_id", "command_key", name="uq_meal_records_user_command_key"),
        Index("ix_meal_records_user_consumed_active", "user_id", "consumed_at", "id", postgresql_where=text("deleted_at IS NULL")),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    source_run_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("agent_runs.id", ondelete="RESTRICT"), nullable=False)
    agent_thread_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("agent_threads.id", ondelete="RESTRICT"), nullable=False)
    agent_run_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("agent_runs.id", ondelete="RESTRICT"), nullable=False)
    command_key: Mapped[str] = mapped_column(String(128), nullable=False)
    consumed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    nutrition_catalog_version: Mapped[str] = mapped_column(String(80), nullable=False)
    calculation_version: Mapped[str] = mapped_column(String(80), nullable=False)
    energy_kcal: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    protein_g: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    fat_g: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    carbohydrate_g: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    items: Mapped[list["MealRecordItem"]] = relationship(back_populates="record", cascade="all, delete-orphan")


class MealRecordItem(Base):
    """An item-level nutrition snapshot, not a live reference to the nutrition catalog."""

    __tablename__ = "meal_record_items"
    __table_args__ = (
        CheckConstraint("position >= 0", name="ck_meal_record_items_position_nonnegative"),
        CheckConstraint("grams > 0", name="ck_meal_record_items_grams_positive"),
        CheckConstraint("energy_kcal >= 0 AND protein_g >= 0 AND fat_g >= 0 AND carbohydrate_g >= 0", name="ck_meal_record_items_nonnegative_nutrients"),
        UniqueConstraint("record_id", "position", name="uq_meal_record_items_record_position"),
        Index("ix_meal_record_items_record_position", "record_id", "position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    record_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("meal_records.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    food_reference: Mapped[str] = mapped_column(String(120), nullable=False)
    grams: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    energy_kcal: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    protein_g: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    fat_g: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    carbohydrate_g: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    is_estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    record: Mapped[MealRecord] = relationship(back_populates="items")


class PreferenceMemoryLedger(Base):
    """Local authorization fact for a safe external preference memory, never raw conversation."""

    __tablename__ = "preference_memory_ledger"
    __table_args__ = (
        CheckConstraint("category IN ('goal', 'avoidance', 'stable_preference')", name="ck_preference_memory_ledger_category"),
        CheckConstraint("source_kind IN ('user_statement', 'model_inference', 'user_maintained')", name="ck_preference_memory_ledger_source_kind"),
        CheckConstraint("canonical_text = btrim(canonical_text) AND canonical_text <> ''", name="ck_preference_memory_ledger_canonical_text"),
        CheckConstraint("provisioning_status IN ('pending', 'claimed', 'provisioned', 'outcome_unknown', 'failed', 'cancelled')", name="ck_preference_memory_ledger_provisioning_status"),
        Index("ix_preference_memory_ledger_user_active", "user_id", "category", "updated_at", postgresql_where=text("is_active")),
        Index("uq_preference_memory_ledger_active_canonical", "user_id", "category", "canonical_text", unique=True, postgresql_where=text("is_active AND deleted_at IS NULL")),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    source_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("agent_runs.id", ondelete="SET NULL"))
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    canonical_text: Mapped[str] = mapped_column(Text, nullable=False)
    request_key_digest: Mapped[str | None] = mapped_column(String(64))
    provisioning_status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    external_memory_id: Mapped[str | None] = mapped_column(String(160))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MemoryDeletionOutbox(Base):
    """Durable cleanup intent; local invisibility is immediate even if external cleanup retries."""

    __tablename__ = "memory_deletion_outbox"
    __table_args__ = (
        CheckConstraint("operation IN ('delete_external_memory')", name="ck_memory_deletion_outbox_operation"),
        CheckConstraint("status IN ('pending', 'processing', 'completed', 'failed')", name="ck_memory_deletion_outbox_status"),
        CheckConstraint("attempt >= 0", name="ck_memory_deletion_outbox_attempt"),
        UniqueConstraint("ledger_id", "operation", name="uq_memory_deletion_outbox_ledger_operation"),
        Index("ix_memory_deletion_outbox_status_not_before", "status", "not_before"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    ledger_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("preference_memory_ledger.id", ondelete="CASCADE"), nullable=False)
    operation: Mapped[str] = mapped_column(String(48), nullable=False)
    request_key: Mapped[str | None] = mapped_column(String(64))
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    not_before: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MemoryProvisionOutbox(Base):
    """Durable, cancellable intent for a single direct-memory provider write."""

    __tablename__ = "memory_provision_outbox"
    __table_args__ = (
        CheckConstraint("operation IN ('provision_external_memory')", name="ck_memory_provision_outbox_operation"),
        CheckConstraint("status IN ('pending', 'claimed', 'provisioned', 'outcome_unknown', 'failed', 'cancelled')", name="ck_memory_provision_outbox_status"),
        CheckConstraint("attempt >= 0", name="ck_memory_provision_outbox_attempt"),
        UniqueConstraint("ledger_id", "operation", name="uq_memory_provision_outbox_ledger_operation"),
        Index("ix_memory_provision_outbox_status_not_before", "status", "not_before"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    ledger_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("preference_memory_ledger.id", ondelete="CASCADE"), nullable=False)
    operation: Mapped[str] = mapped_column(String(48), nullable=False)
    request_key: Mapped[str] = mapped_column(String(64), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    not_before: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
