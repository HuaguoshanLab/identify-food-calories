"""Pure deterministic fusion for non-exact hybrid food retrieval evidence."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.nutrition.schemas import (
    MAX_CANDIDATE_PORTION_HINTS,
    FoodRelation,
    FoodSearchCandidate,
    FoodSearchEvidence,
    FoodSearchFusionResult,
)


TEXT_SCORE_THRESHOLD = Decimal("0.30")
VECTOR_SCORE_THRESHOLD = Decimal("0.55")
RRF_OFFSET = Decimal("60")

_RELATION_LAYER = {
    FoodRelation.NAME_VARIANT: 0,
    FoodRelation.REGIONAL_PREPARATION_VARIANT: 1,
    FoodRelation.SAME_CLASS: 2,
}


@dataclass(frozen=True, slots=True)
class _MergedEvidence:
    food_evidence: FoodSearchEvidence
    text_rank: int | None
    vector_rank: int | None
    text_score: Decimal | None
    vector_score: Decimal | None


def fuse_food_search_evidence(
    evidence: list[FoodSearchEvidence],
) -> FoodSearchFusionResult:
    """Dedupe reliable evidence then rank relation layers before in-layer RRF."""

    merged: dict[tuple[str, str], _MergedEvidence] = {}
    for hit in evidence:
        if not _is_reliable(hit):
            continue
        identity = (str(hit.food.id), hit.food.catalog_version)
        previous = merged.get(identity)
        merged[identity] = _merge(previous, hit) if previous is not None else _MergedEvidence(
            food_evidence=hit,
            text_rank=hit.text_rank,
            vector_rank=hit.vector_rank,
            text_score=hit.text_score,
            vector_score=hit.vector_score,
        )

    ordered = sorted(merged.values(), key=_rank_key)
    return FoodSearchFusionResult(
        candidates=tuple(
            project_food_search_candidate(item.food_evidence)
            for item in ordered[:3]
        )
    )


def project_food_search_candidate(evidence: FoodSearchEvidence) -> FoodSearchCandidate:
    """Project only D-04 allowlisted discriminators to callers and checkpoint state."""

    food = evidence.food
    return FoodSearchCandidate(
        food_id=food.id,
        catalog_version=food.catalog_version,
        canonical_name=food.canonical_name,
        relation=evidence.relation,
        prepared_state=food.prepared_state or None,
        portion_hints=tuple(
            portion.description
            for portion in food.portions
            if portion.audited
        )[:MAX_CANDIDATE_PORTION_HINTS],
        source_name=food.source_name,
    )


def _is_reliable(hit: FoodSearchEvidence) -> bool:
    """Reject weak channel hits instead of using them as Top-3 filler."""

    return (
        hit.text_score is not None and hit.text_score >= TEXT_SCORE_THRESHOLD
    ) or (
        hit.vector_score is not None and hit.vector_score >= VECTOR_SCORE_THRESHOLD
    )


def _merge(previous: _MergedEvidence, current: FoodSearchEvidence) -> _MergedEvidence:
    """Keep the strongest relation, preserving each channel's best stable rank."""

    previous_evidence = previous.food_evidence
    winner = min(
        (previous_evidence, current),
        key=lambda hit: (
            _RELATION_LAYER[hit.relation],
            str(hit.food.id),
            hit.food.catalog_version,
        ),
    )
    return _MergedEvidence(
        food_evidence=winner,
        text_rank=_lowest_rank(previous.text_rank, current.text_rank),
        vector_rank=_lowest_rank(previous.vector_rank, current.vector_rank),
        text_score=_highest_score(previous.text_score, current.text_score),
        vector_score=_highest_score(previous.vector_score, current.vector_score),
    )


def _rank_key(item: _MergedEvidence) -> tuple[int, Decimal, Decimal, int, int, str, str]:
    evidence = item.food_evidence
    text_rank = item.text_rank or 10_000
    vector_rank = item.vector_rank or 10_000
    rrf = sum(
        (Decimal(1) / (RRF_OFFSET + rank) for rank in (item.text_rank, item.vector_rank) if rank),
        start=Decimal(0),
    )
    best_score = max(
        (score for score in (item.text_score, item.vector_score) if score is not None),
        default=Decimal(0),
    )
    return (
        _RELATION_LAYER[evidence.relation],
        -best_score,
        -rrf,
        text_rank,
        vector_rank,
        evidence.food.catalog_version,
        str(evidence.food.id),
    )


def _lowest_rank(left: int | None, right: int | None) -> int | None:
    return min(rank for rank in (left, right) if rank is not None) if left or right else None


def _highest_score(left: Decimal | None, right: Decimal | None) -> Decimal | None:
    return max(score for score in (left, right) if score is not None) if left or right else None
