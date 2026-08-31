"""pgvector-backed metadata records; embeddings never leave repository scope."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UserDefinedType

from app.auth.models import Base


class Vector(UserDefinedType[str]):
    """Small fixed dimension type without introducing a second vector ORM dependency."""

    cache_ok = True

    def get_col_spec(self, **_kw: object) -> str:
        return "vector(3)"


class MealHistoryEmbedding(Base):
    __tablename__ = "meal_history_embeddings"
    __table_args__ = (
        CheckConstraint("source_type = 'meal_history'", name="ck_meal_history_embeddings_source_type"),
        CheckConstraint("embedding_model = btrim(embedding_model) AND embedding_model <> ''", name="ck_meal_history_embeddings_model"),
        CheckConstraint("embedding_version = btrim(embedding_version) AND embedding_version <> ''", name="ck_meal_history_embeddings_version"),
        Index("ix_meal_history_embeddings_user_active", "user_id", "created_at", postgresql_where="is_active AND deleted_at IS NULL"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    meal_record_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("meal_records.id", ondelete="CASCADE"), nullable=False, unique=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="meal_history")
    embedding_model: Mapped[str] = mapped_column(String(120), nullable=False)
    embedding_version: Mapped[str] = mapped_column(String(80), nullable=False)
    embedding: Mapped[str] = mapped_column(Vector(), nullable=False)
    safe_summary: Mapped[str] = mapped_column(String(500), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NutritionKnowledgeEmbedding(Base):
    __tablename__ = "nutrition_knowledge_embeddings"
    __table_args__ = (
        CheckConstraint("source_type = 'nutrition_knowledge'", name="ck_nutrition_knowledge_embeddings_source_type"),
        CheckConstraint("embedding_model = btrim(embedding_model) AND embedding_model <> ''", name="ck_nutrition_knowledge_embeddings_model"),
        CheckConstraint("embedding_version = btrim(embedding_version) AND embedding_version <> ''", name="ck_nutrition_knowledge_embeddings_version"),
        Index("ix_nutrition_knowledge_embeddings_eligible", "catalog_version", "created_at", postgresql_where="is_eligible AND deleted_at IS NULL"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    food_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("food_catalog_items.id", ondelete="CASCADE"), nullable=False)
    catalog_version: Mapped[str] = mapped_column(String(80), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="nutrition_knowledge")
    embedding_model: Mapped[str] = mapped_column(String(120), nullable=False)
    embedding_version: Mapped[str] = mapped_column(String(80), nullable=False)
    embedding: Mapped[str] = mapped_column(Vector(), nullable=False)
    safe_summary: Mapped[str] = mapped_column(String(500), nullable=False)
    is_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
