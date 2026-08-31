"""Create pgvector metadata records for source-separated retrieval.

Revision ID: 0008
Revises: 0007
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | None = None
depends_on: str | None = None


class _Vector(sa.types.UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **_kw: object) -> str:
        return "vector(3)"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    vector = _Vector()
    op.create_table(
        "meal_history_embeddings",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("user_id", sa.Uuid(), nullable=False), sa.Column("meal_record_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False), sa.Column("embedding_model", sa.String(120), nullable=False), sa.Column("embedding_version", sa.String(80), nullable=False),
        sa.Column("embedding", vector, nullable=False), sa.Column("safe_summary", sa.String(500), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("source_type = 'meal_history'", name="ck_meal_history_embeddings_source_type"), sa.CheckConstraint("embedding_model = btrim(embedding_model) AND embedding_model <> ''", name="ck_meal_history_embeddings_model"), sa.CheckConstraint("embedding_version = btrim(embedding_version) AND embedding_version <> ''", name="ck_meal_history_embeddings_version"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_meal_history_embeddings_user_id", ondelete="CASCADE"), sa.ForeignKeyConstraint(["meal_record_id"], ["meal_records.id"], name="fk_meal_history_embeddings_meal_record_id", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_meal_history_embeddings"), sa.UniqueConstraint("meal_record_id", name="uq_meal_history_embeddings_meal_record_id"),
    )
    op.create_index("ix_meal_history_embeddings_user_active", "meal_history_embeddings", ["user_id", "created_at"], unique=False, postgresql_where=sa.text("is_active AND deleted_at IS NULL"))
    op.create_table(
        "nutrition_knowledge_embeddings",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("food_id", sa.Uuid(), nullable=False), sa.Column("catalog_version", sa.String(80), nullable=False), sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("embedding_model", sa.String(120), nullable=False), sa.Column("embedding_version", sa.String(80), nullable=False), sa.Column("embedding", vector, nullable=False), sa.Column("safe_summary", sa.String(500), nullable=False), sa.Column("is_eligible", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("source_type = 'nutrition_knowledge'", name="ck_nutrition_knowledge_embeddings_source_type"), sa.CheckConstraint("embedding_model = btrim(embedding_model) AND embedding_model <> ''", name="ck_nutrition_knowledge_embeddings_model"), sa.CheckConstraint("embedding_version = btrim(embedding_version) AND embedding_version <> ''", name="ck_nutrition_knowledge_embeddings_version"),
        sa.ForeignKeyConstraint(["food_id"], ["food_catalog_items.id"], name="fk_nutrition_knowledge_embeddings_food_id", ondelete="CASCADE"), sa.PrimaryKeyConstraint("id", name="pk_nutrition_knowledge_embeddings"),
    )
    op.create_index("ix_nutrition_knowledge_embeddings_eligible", "nutrition_knowledge_embeddings", ["catalog_version", "created_at"], unique=False, postgresql_where=sa.text("is_eligible AND deleted_at IS NULL"))


def downgrade() -> None:
    op.drop_index("ix_nutrition_knowledge_embeddings_eligible", table_name="nutrition_knowledge_embeddings")
    op.drop_table("nutrition_knowledge_embeddings")
    op.drop_index("ix_meal_history_embeddings_user_active", table_name="meal_history_embeddings")
    op.drop_table("meal_history_embeddings")
