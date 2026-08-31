"""Exact SQL retrieval with tenant and eligibility predicates before any result is materialized."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.nutrition.models import FoodCatalogItem
from app.records.models import MealRecord
from app.retrieval.models import MealHistoryEmbedding, NutritionKnowledgeEmbedding
from app.retrieval.ports import RetrievedContextItem


class SqlAlchemyRetrievalRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_personal_history(self, *, user_id: uuid.UUID, query: str, limit: int) -> list[RetrievedContextItem]:
        statement = (
            select(MealHistoryEmbedding.safe_summary, MealRecord.consumed_at)
            .join(MealRecord, MealRecord.id == MealHistoryEmbedding.meal_record_id)
            .where(
                MealHistoryEmbedding.user_id == user_id,
                MealHistoryEmbedding.is_active.is_(True),
                MealHistoryEmbedding.deleted_at.is_(None),
                MealRecord.user_id == user_id,
                MealRecord.deleted_at.is_(None),
                MealHistoryEmbedding.safe_summary.ilike(f"%{query}%"),
            )
            .order_by(MealRecord.consumed_at.desc(), MealHistoryEmbedding.id.desc())
            .limit(limit)
        )
        return [RetrievedContextItem(source="meal_history", summary=summary, occurred_at=consumed_at) for summary, consumed_at in self._session.execute(statement)]

    def list_nutrition_knowledge(self, *, query: str, catalog_version: str | None, limit: int) -> list[RetrievedContextItem]:
        if catalog_version is None:
            # Knowledge is version-bound. Returning a cross-version mixture would defeat the
            # controlled catalog contract, so absent version means no knowledge recall.
            return []
        statement = (
            select(NutritionKnowledgeEmbedding.safe_summary)
            .join(FoodCatalogItem, FoodCatalogItem.id == NutritionKnowledgeEmbedding.food_id)
            .where(
                NutritionKnowledgeEmbedding.is_eligible.is_(True),
                NutritionKnowledgeEmbedding.deleted_at.is_(None),
                NutritionKnowledgeEmbedding.catalog_version == catalog_version,
                FoodCatalogItem.is_qualified.is_(True),
                NutritionKnowledgeEmbedding.safe_summary.ilike(f"%{query}%"),
            )
            .order_by(NutritionKnowledgeEmbedding.created_at.desc(), NutritionKnowledgeEmbedding.id.desc())
            .limit(limit)
        )
        return [RetrievedContextItem(source="nutrition_knowledge", summary=summary) for summary in self._session.scalars(statement)]
