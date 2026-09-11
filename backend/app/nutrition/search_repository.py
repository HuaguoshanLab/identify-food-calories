"""PostgreSQL adapter for the versioned hybrid food-search boundary.

The adapter deliberately reads only current, eligible catalog publications.  Search
indexes are derived data, so neither an old vector nor a stale relation assertion
can make a publication usable after its authoritative lifecycle changes.
"""

from __future__ import annotations

import math
import uuid
from decimal import Decimal

from sqlalchemy import Select, bindparam, case, desc, func, select
from sqlalchemy.orm import Session, aliased

from app.admin.models import CatalogPublication
from app.nutrition.repository import ADMIN_PUBLICATION_VERSION, SqlAlchemyNutritionRepository
from app.nutrition.schemas import FoodRelation, FoodSearchEvidence, QualifiedFood
from app.nutrition.search_models import (
    CatalogActiveVectorSpace,
    CatalogSearchEmbedding,
    CatalogSearchName,
    CatalogSearchRelationEvidence,
    CatalogSearchVersion,
    CatalogVectorSpace,
)


_TEXT_MIN_SIMILARITY = Decimal("0.20")
_VECTOR_DIMENSION = 1024


class SqlAlchemyHybridFoodSearchRepository:
    """Authoritative three-channel adapter; callers still own PASS/ASK semantics."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_current_qualified_exact(self, *, normalized_query: str) -> list[QualifiedFood]:
        statement = (
            self._current_qualified_statement()
            .join(CatalogSearchName, CatalogSearchName.publication_id == CatalogPublication.id)
            .where(CatalogSearchName.normalized_name == bindparam("normalized_query", normalized_query))
            .order_by(CatalogPublication.id)
        )
        return [SqlAlchemyNutritionRepository._to_published_food(row) for row in self._session.scalars(statement).unique()]

    def find_text_candidates(self, *, normalized_query: str, limit: int) -> list[FoodSearchEvidence]:
        if limit <= 0:
            return []
        similarity = func.similarity(
            CatalogSearchName.normalized_name,
            bindparam("normalized_query", normalized_query),
        )
        relation = self._current_relation_for_text_query(normalized_query)
        statement = (
            self._current_qualified_statement()
            .join(CatalogSearchName, CatalogSearchName.publication_id == CatalogPublication.id)
            .add_columns(CatalogSearchName, similarity.label("score"), relation.label("relation"))
            .where(similarity >= _TEXT_MIN_SIMILARITY)
            .order_by(desc(similarity), CatalogSearchName.normalized_name, CatalogPublication.id)
            .limit(limit)
        )
        return [
            FoodSearchEvidence(
                food=SqlAlchemyNutritionRepository._to_published_food(publication),
                relation=self._relation_or_conservative_default(relation_value),
                text_rank=rank,
                text_score=Decimal(str(score)),
            )
            for rank, (publication, _name, score, relation_value) in enumerate(self._session.execute(statement), start=1)
        ]

    def find_vector_candidates(
        self, *, query_vector: tuple[float, ...], limit: int
    ) -> list[FoodSearchEvidence]:
        if limit <= 0:
            return []
        if len(query_vector) != _VECTOR_DIMENSION or not all(math.isfinite(value) for value in query_vector):
            raise ValueError("query vector must be a finite 1024-dimension vector")

        distance = CatalogSearchEmbedding.embedding.cosine_distance(list(query_vector))
        statement = (
            self._current_qualified_statement()
            .join(CatalogSearchName, CatalogSearchName.publication_id == CatalogPublication.id)
            .join(CatalogSearchEmbedding, CatalogSearchEmbedding.name_id == CatalogSearchName.id)
            .join(CatalogActiveVectorSpace, CatalogActiveVectorSpace.vector_space_id == CatalogSearchEmbedding.vector_space_id)
            .join(CatalogVectorSpace, CatalogVectorSpace.id == CatalogActiveVectorSpace.vector_space_id)
            .add_columns(CatalogSearchName, distance.label("distance"))
            .where(
                CatalogSearchEmbedding.status == "ready",
                CatalogVectorSpace.embedding_dimension == _VECTOR_DIMENSION,
            )
            .order_by(distance, CatalogSearchName.normalized_name, CatalogPublication.id)
            .limit(limit)
        )
        return [
            FoodSearchEvidence(
                food=SqlAlchemyNutritionRepository._to_published_food(publication),
                relation=FoodRelation.SAME_CLASS,
                vector_rank=rank,
                vector_score=Decimal(str(max(0.0, 1.0 - float(distance_value)))),
            )
            for rank, (publication, _name, distance_value) in enumerate(self._session.execute(statement), start=1)
        ]

    def get_current_qualified_food(
        self, *, food_id: uuid.UUID, catalog_version: str
    ) -> QualifiedFood | None:
        if catalog_version != ADMIN_PUBLICATION_VERSION:
            return None
        publication = self._session.scalar(
            self._current_qualified_statement().where(CatalogPublication.id == food_id)
        )
        return SqlAlchemyNutritionRepository._to_published_food(publication) if publication is not None else None

    @staticmethod
    def _current_qualified_statement() -> Select[tuple[CatalogPublication]]:
        """One live authority predicate shared by all channels and confirmation."""
        return SqlAlchemyNutritionRepository.current_qualified_publication_statement()

    def _current_relation_for_text_query(self, normalized_query: str):
        """Use relation evidence only when both endpoints are current content versions."""

        source_name = aliased(CatalogSearchName)
        source_publication = aliased(CatalogPublication)
        source_version = aliased(CatalogSearchVersion)
        target_version = aliased(CatalogSearchVersion)
        source_current = self._current_qualified_statement().with_only_columns(CatalogPublication.id).subquery()
        target_current = self._current_qualified_statement().with_only_columns(CatalogPublication.id).subquery()
        return (
            select(CatalogSearchRelationEvidence.relation)
            .join(source_name, source_name.id == CatalogSearchRelationEvidence.source_name_id)
            .join(source_publication, source_publication.id == source_name.publication_id)
            .join(source_version, source_version.id == source_name.search_version_id)
            .join(target_version, target_version.id == CatalogSearchName.search_version_id)
            .where(
                CatalogSearchRelationEvidence.target_name_id == CatalogSearchName.id,
                CatalogSearchRelationEvidence.status == "active",
                source_name.normalized_name == bindparam("relation_query", normalized_query),
                source_publication.id.in_(select(source_current.c.id)),
                CatalogSearchName.publication_id.in_(select(target_current.c.id)),
                source_version.content_hash == source_publication.content_hash,
                target_version.content_hash == CatalogPublication.content_hash,
            )
            .order_by(
                case(
                    (CatalogSearchRelationEvidence.relation == "name_variant", 0),
                    (CatalogSearchRelationEvidence.relation == "regional_preparation_variant", 1),
                    else_=2,
                ),
                CatalogSearchRelationEvidence.occurred_at.desc(),
            )
            .limit(1)
            .scalar_subquery()
        )

    @staticmethod
    def _relation_or_conservative_default(value: str | None) -> FoodRelation:
        return {
            "name_variant": FoodRelation.NAME_VARIANT,
            "regional_preparation_variant": FoodRelation.REGIONAL_PREPARATION_VARIANT,
            "same_category_food": FoodRelation.SAME_CLASS,
        }.get(value, FoodRelation.SAME_CLASS)
