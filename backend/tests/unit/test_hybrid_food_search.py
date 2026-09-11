"""Pure contracts for versioned hybrid-food candidate fusion."""

from __future__ import annotations

import json
import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.nutrition.schemas import (
    ControlledPortion,
    FoodRelation,
    FoodSearchCandidate,
    FoodSearchEvidence,
    NutritionValues,
    QualifiedFood,
)
from app.nutrition.search import fuse_food_search_evidence, project_food_search_candidate


def make_food(
    *,
    food_id: uuid.UUID | None = None,
    name: str = "番茄炒蛋",
    prepared_state: str = "炒制",
    source_name: str = "受控目录",
    portions: tuple[ControlledPortion, ...] = (),
) -> QualifiedFood:
    return QualifiedFood(
        id=food_id or uuid.uuid4(),
        canonical_name=name,
        catalog_version="catalog-2026-09",
        prepared_state=prepared_state,
        source_name=source_name,
        source_url="https://example.test/catalog",
        license_name="CC0",
        aliases=(name,),
        portions=portions,
        nutrients_per_100g=NutritionValues(
            energy_kcal=Decimal("100"),
            protein_g=Decimal("5"),
            fat_g=Decimal("4"),
            carbohydrate_g=Decimal("10"),
        ),
    )


def evidence(
    food: QualifiedFood,
    *,
    relation: FoodRelation = FoodRelation.NAME_VARIANT,
    text_rank: int | None = 1,
    vector_rank: int | None = None,
    text_score: Decimal | None = Decimal("0.8"),
    vector_score: Decimal | None = None,
) -> FoodSearchEvidence:
    return FoodSearchEvidence(
        food=food,
        relation=relation,
        text_rank=text_rank,
        vector_rank=vector_rank,
        text_score=text_score,
        vector_score=vector_score,
    )


def test_fusion_invariant_never_selects_nonexact_and_returns_at_most_three() -> None:
    foods = [make_food(name=f"候选{index}") for index in range(4)]

    result = fuse_food_search_evidence([evidence(food, text_rank=index + 1) for index, food in enumerate(foods)])

    assert result.selected_food is None
    assert len(result.candidates) == 3
    assert tuple(candidate.canonical_name for candidate in result.candidates) == ("候选0", "候选1", "候选2")


def test_fusion_deduplicates_identity_and_combines_channel_ranks() -> None:
    food = make_food(name="番茄炒蛋")

    result = fuse_food_search_evidence(
        [
            evidence(food, relation=FoodRelation.SAME_CLASS, text_rank=2, text_score=Decimal("0.9")),
            evidence(
                food,
                relation=FoodRelation.NAME_VARIANT,
                text_rank=None,
                vector_rank=1,
                text_score=None,
                vector_score=Decimal("0.9"),
            ),
        ]
    )

    assert len(result.candidates) == 1
    assert result.candidates[0].relation is FoodRelation.NAME_VARIANT


def test_fusion_keeps_layer_order_before_equal_scores_and_uses_stable_identity_tiebreaker() -> None:
    first_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    second_id = uuid.UUID("00000000-0000-0000-0000-000000000002")
    name_variant = make_food(food_id=second_id, name="西红柿炒鸡蛋")
    same_class = make_food(food_id=first_id, name="鸡蛋羹")
    equal_a = make_food(food_id=first_id, name="番茄炒蛋 A")
    equal_b = make_food(food_id=second_id, name="番茄炒蛋 B")

    layered = fuse_food_search_evidence(
        [
            evidence(same_class, relation=FoodRelation.SAME_CLASS, text_score=Decimal("0.99")),
            evidence(name_variant, relation=FoodRelation.NAME_VARIANT, text_score=Decimal("0.30")),
        ]
    )
    equal = fuse_food_search_evidence(
        [
            evidence(equal_b, text_score=Decimal("0.8")),
            evidence(equal_a, text_score=Decimal("0.8")),
        ]
    )

    assert tuple(candidate.canonical_name for candidate in layered.candidates) == ("西红柿炒鸡蛋", "鸡蛋羹")
    assert tuple(candidate.food_id for candidate in equal.candidates) == (first_id, second_id)


def test_fusion_returns_fewer_than_three_and_drops_shared_ingredient_noise() -> None:
    reliable = make_food(name="牛肉干")
    shared_ingredient_noise = make_food(name="番茄牛腩")

    result = fuse_food_search_evidence(
        [
            evidence(reliable, relation=FoodRelation.REGIONAL_PREPARATION_VARIANT),
            evidence(
                shared_ingredient_noise,
                relation=FoodRelation.SAME_CLASS,
                text_score=Decimal("0.29"),
            ),
        ]
    )

    assert tuple(candidate.canonical_name for candidate in result.candidates) == ("牛肉干",)


def test_fusion_keeps_one_reliable_nonexact_hit_without_selection() -> None:
    result = fuse_food_search_evidence(
        [evidence(make_food(name="烤鱼"), relation=FoodRelation.REGIONAL_PREPARATION_VARIANT)]
    )

    assert result.selected_food is None
    assert tuple(candidate.canonical_name for candidate in result.candidates) == ("烤鱼",)


def test_public_candidate_projects_only_safe_discriminators_and_bounded_portions() -> None:
    food = make_food(
        portions=tuple(
            ControlledPortion(
                description=f"份量{index}",
                grams=Decimal(index + 1),
                source_reference="https://example.test/portion",
                version="v1",
            )
            for index in range(4)
        )
    )

    candidate = project_food_search_candidate(evidence(food))
    serialized = candidate.model_dump(mode="json")

    assert candidate.prepared_state == "炒制"
    assert candidate.portion_hints == ("份量0", "份量1", "份量2")
    assert candidate.source_name == "受控目录"
    assert set(serialized) == {
        "food_id",
        "catalog_version",
        "canonical_name",
        "relation",
        "prepared_state",
        "portion_hints",
        "source_name",
    }
    encoded = json.dumps(serialized, ensure_ascii=False)
    assert "score" not in encoded
    assert "rank" not in encoded
    assert "vector" not in encoded
    assert "provider" not in encoded


def test_discriminator_projection_allows_absent_prepared_state_and_rejects_internal_fields() -> None:
    candidate = FoodSearchCandidate(
        food_id=uuid.uuid4(),
        catalog_version="catalog-2026-09",
        canonical_name="土豆粉",
        relation=FoodRelation.SAME_CLASS,
        source_name="受控目录",
    )

    assert candidate.prepared_state is None
    assert candidate.portion_hints == ()
    with pytest.raises(ValidationError):
        FoodSearchCandidate.model_validate(
            {
                **candidate.model_dump(),
                "similarity_score": 0.9,
            }
        )
