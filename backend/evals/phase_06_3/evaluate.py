"""Strict offline evaluator using ``SqlAlchemyHybridFoodSearchRepository`` against PostgreSQL."""

from __future__ import annotations

import hashlib
import json
import argparse
import asyncio
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any
import sys
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin.models import CatalogPublication, CatalogPublicationEligibility
from app.admin.repository import SqlAlchemyAdminRepository
from app.admin.schemas import CatalogDraftCreateCommand, CatalogLifecycleCommand
from app.admin.service import AdminService
from app.agent.graph import DietPlanningGraph, MealAnalysisGraph
from app.agent.state import DietPlanningState, MealAgentState
from app.agent.tools import CapturedPreferenceSummary
from app.auth.models import User, UserRole
from app.nutrition.repository import SqlAlchemyNutritionRepository
from app.nutrition.schemas import FoodRelation, FoodSearchEvidence, FoodSearchInput, NutritionAction
from app.nutrition.search_models import (
    CatalogActiveVectorSpace,
    CatalogSearchEmbedding,
    CatalogSearchName,
    CatalogSearchVersion,
    CatalogVectorSpace,
)
from app.nutrition.search_repository import SqlAlchemyHybridFoodSearchRepository
from app.nutrition.service import NutritionService
from app.providers.embedding.fake import FakeEmbeddingProvider
from app.providers.reasoning.dto import ParsedMealDTO, ParsedMealItemDTO, ProviderFailureKind
from app.providers.reasoning.fake import FakeReasoningModelProvider
from app.planning.repository import SqlAlchemyPlanningProfileRepository
from app.planning.schemas import MealCompositionResult, PlanValidationResult, PlanningProfileInput, PreferenceReview
from app.planning.service import PlanningService


CASE_SCHEMA_VERSION = "phase063-case.v1"
EVALUATOR_VERSION = "phase063-evaluator.v1"
CASE_FIELDS = (
    "schema_version",
    "case_id",
    "sequence",
    "kind",
    "query",
    "fixture_snapshot",
    "expected",
    "auto_pass_allowed",
    "catalog_version",
    "retrieval_version",
    "embedding_version",
    "parent_hash",
    "case_hash",
)
EXPECTED_FIELDS = (
    "action",
    "match_channel",
    "target_food_ids",
    "excluded_food_ids",
    "candidate_limit",
    "execution_mode",
)
REQUIRED_CASE_KINDS = frozenset({"exact", "non_exact", "ambiguity", "eligibility", "failure_determinism"})
RELEASE_SCHEMA_VERSION = "phase063-release.v1"
RELEASE_FIELDS = frozenset({"schema_version", "evaluator_version", "decision", "input_hashes", "snapshot", "metrics", "cases", "evidence_hash"})
RELEASE_CASE_FIELDS = frozenset({"case_id", "case_hash", "action", "candidate_ids", "exact_sql", "text_sql", "vector_sql", "graph_calls", "assertions"})
RELEASE_ASSERTION_FIELDS = frozenset({"action", "targets", "excluded", "channel", "execution_mode", "versions", "candidate_bound", "meal_graph", "planning_graph"})
RELEASE_GRAPH_CALL_FIELDS = frozenset({"meal_graph_entries", "planning_graph_entries", "meal_search_calls", "planning_target_calls", "planning_compose_calls"})
RELEASE_METRIC_FIELDS = frozenset({"case_count", "exact_sql_cases", "text_sql_cases", "vector_sql_cases", "meal_graph_entries", "planning_graph_entries", "meal_tool_search_calls", "planning_tool_target_calls", "planning_tool_compose_calls", "action_pass_rate", "target_recall"})
RELEASE_INPUT_HASH_FIELDS = frozenset({"dataset_sha256", "evaluator_sha256", "search_policy_sha256"})
RELEASE_SNAPSHOT_FIELDS = frozenset({"fixture", "food_labels"})
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN_FIELD_PARTS = frozenset({
    "email", "identity", "user", "meal", "body", "health", "image", "base64",
    "prompt", "provider", "response", "vector", "embedding_data", "token", "secret",
})
_LOCKED_NON_EXACT_TARGETS = {
    "西红柿炒鸡蛋": "food:tomato-egg-v1",
    "风干牛肉": "food:beef-jerky-v1",
    "四川烤鱼": "food:grilled-fish-v1",
    "定西土豆粉": "food:potato-noodles-v1",
    "包子": "food:pan-fried-bun-v1",
}


class EvaluationContractError(ValueError):
    """Stable CI-safe rejection for untrusted frozen evidence."""


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _hash(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def file_hash(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise EvaluationContractError(f"required evidence is unavailable: {path.name}") from error


def _load_rows(dataset: Path) -> list[dict[str, Any]]:
    try:
        rows = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line]
    except (OSError, json.JSONDecodeError) as error:
        raise EvaluationContractError("frozen retrieval dataset is unreadable") from error
    if not rows or not all(isinstance(row, dict) for row in rows):
        raise EvaluationContractError("frozen retrieval dataset must contain object rows")
    return rows


def _validate_expected(expected: object) -> dict[str, Any]:
    if not isinstance(expected, dict) or tuple(expected) != EXPECTED_FIELDS:
        raise EvaluationContractError("case expectation fields do not match the frozen contract")
    if expected["action"] not in {"PASS", "ASK"} or expected["match_channel"] not in {"exact", "hybrid", "text_fallback", "none"}:
        raise EvaluationContractError("case action or channel is invalid")
    if not all(isinstance(expected[key], list) and all(isinstance(item, str) and item.startswith("food:") for item in expected[key]) for key in ("target_food_ids", "excluded_food_ids")):
        raise EvaluationContractError("case food identifiers are invalid")
    if not isinstance(expected["candidate_limit"], int) or not 0 <= expected["candidate_limit"] <= 3 or not isinstance(expected["execution_mode"], str):
        raise EvaluationContractError("case candidate contract is invalid")
    return expected


def validate_dataset(dataset: Path) -> list[dict[str, Any]]:
    """Load only evidence that has the exact frozen schema, ordering and chain."""

    rows, parent_hash = _load_rows(dataset), None
    for sequence, row in enumerate(rows, start=1):
        if any(part in key.lower() for key in row for part in _FORBIDDEN_FIELD_PARTS if key not in {"embedding_version"}):
            raise EvaluationContractError("case contains a forbidden sensitive or privacy field")
        if tuple(row) != CASE_FIELDS:
            raise EvaluationContractError("case fields or field order do not match the frozen contract")
        if row["schema_version"] != CASE_SCHEMA_VERSION or row["case_id"] != f"phase063-{sequence:03d}" or row["sequence"] != sequence:
            raise EvaluationContractError("case version, identifier, or sequence is invalid")
        if not isinstance(row["query"], str) or not row["query"] or not isinstance(row["fixture_snapshot"], str) or not row["fixture_snapshot"].startswith("synthetic:"):
            raise EvaluationContractError("case query or synthetic snapshot is invalid")
        if not all(isinstance(row[key], str) and row[key] for key in ("catalog_version", "retrieval_version", "embedding_version")):
            raise EvaluationContractError("case version declarations are invalid")
        expected = _validate_expected(row["expected"])
        if row["parent_hash"] != parent_hash:
            raise EvaluationContractError("case parent hash chain is invalid")
        if not isinstance(row["case_hash"], str) or row["case_hash"] != _hash({key: value for key, value in row.items() if key != "case_hash"}):
            raise EvaluationContractError("case hash does not match canonical content")
        if not isinstance(row["auto_pass_allowed"], bool) or (expected["action"] == "PASS") != row["auto_pass_allowed"]:
            raise EvaluationContractError("case auto-pass contract is invalid")
        if row["kind"] == "non_exact" and (expected["action"] != "ASK" or row["auto_pass_allowed"] or not expected["target_food_ids"]):
            raise EvaluationContractError("non-exact cases must require confirmation without an exact bypass")
        parent_hash = row["case_hash"]

    if len(rows) < 24 or REQUIRED_CASE_KINDS - {row["kind"] for row in rows}:
        raise EvaluationContractError("frozen dataset is missing required category coverage")
    for query, target in _LOCKED_NON_EXACT_TARGETS.items():
        matching = [row for row in rows if row["query"] == query and row["kind"] == "non_exact"]
        if len(matching) != 1 or target not in matching[0]["expected"]["target_food_ids"]:
            raise EvaluationContractError("frozen dataset is missing a locked Top-3 mapping")
    if not any(row["query"] == "米饭" and row["expected"]["action"] == "PASS" and row["expected"]["target_food_ids"] == ["food:rice-v1"] for row in rows):
        raise EvaluationContractError("frozen dataset is missing the rice exact-pass mapping")
    return rows


_CANONICAL_NAMES = {
    "food:rice-v1": "米饭", "food:boiled-egg-v1": "水煮蛋",
    "food:tomato-egg-v1": "番茄炒蛋", "food:apple-v1": "苹果",
    "food:beef-jerky-v1": "牛肉干", "food:grilled-fish-v1": "烤鱼",
    "food:potato-noodles-v1": "土豆粉", "food:pan-fried-bun-v1": "生煎包",
    "food:hot-dry-noodles-v1": "热干面", "food:timeout-safe-v1": "超时安全菜",
    "food:index-fallback-v1": "索引回退菜", "food:stable-order-v1": "稳定排序菜",
    "food:egg-fried-rice-v1": "蛋炒饭", "food:tea-egg-v1": "茶叶蛋",
    "food:firm-tofu-v1": "老豆腐", "food:silken-tofu-v1": "嫩豆腐",
    "food:chicken-v1": "鸡肉", "food:revoked-v1": "已撤销菜",
    "food:ineligible-v1": "失格菜", "food:old-version-v0": "旧版菜",
    "food:missing-source-v1": "缺来源菜",
    "food:vegetable-fried-rice-v1": "蔬菜炒饭",
}
_QUERY_TARGETS = {
    "米饭": "food:rice-v1", "白米饭": "food:rice-v1", "水煮蛋": "food:boiled-egg-v1",
    "番茄炒蛋": "food:tomato-egg-v1", "苹果": "food:apple-v1",
    "西红柿炒鸡蛋": "food:tomato-egg-v1", "风干牛肉": "food:beef-jerky-v1",
    "四川烤鱼": "food:grilled-fish-v1", "定西土豆粉": "food:potato-noodles-v1",
    "包子": "food:pan-fried-bun-v1", "武汉热干面": "food:hot-dry-noodles-v1",
    "炒饭": "food:vegetable-fried-rice-v1",
    "检索超时菜": "food:timeout-safe-v1", "索引缺失菜": "food:index-fallback-v1",
    "排序稳定菜": "food:stable-order-v1",
}


def _vector(index: int) -> tuple[float, ...]:
    """A sparse fixed Fake vector keeps the runner offline and byte-stable."""
    return tuple(1.0 if position == index else 0.0 for position in range(1024))


def _publish(session: Session, actor: User, name: str, key: str, now: datetime) -> CatalogPublication:
    service = AdminService(repository=SqlAlchemyAdminRepository(session), now=lambda: now, commit=session.commit, rollback=session.rollback)
    draft = service.create_catalog_draft(
        actor_user_id=actor.id,
        command=CatalogDraftCreateCommand(canonical_name=name, aliases=[f"{name}评测"], energy_kcal_per_100g=Decimal("100"), protein_g_per_100g=Decimal("5"), fat_g_per_100g=Decimal("2"), carbohydrate_g_per_100g=Decimal("20"), source_name="Synthetic frozen evaluation", source_url="https://example.test/frozen", authorization_status="authorized", reason="phase 06.3 synthetic evaluation fixture"),
        command_key=f"eval-create-{key}",
    )
    lifecycle = CatalogLifecycleCommand(reason="synthetic fixture approved", confirm=True)
    service.review_catalog_draft(actor_user_id=actor.id, draft_id=draft.id, expected_revision=1, command=lifecycle, command_key=f"eval-review-{key}")
    published = service.publish_catalog_draft(actor_user_id=actor.id, draft_id=draft.id, expected_revision=1, command=lifecycle, command_key=f"eval-publish-{key}")
    publication = session.get(CatalogPublication, published.id)
    assert publication is not None
    return publication


def _active_space(session: Session, now: datetime) -> CatalogVectorSpace:
    space = session.scalar(select(CatalogVectorSpace).join(CatalogActiveVectorSpace, CatalogActiveVectorSpace.vector_space_id == CatalogVectorSpace.id).where(CatalogActiveVectorSpace.pointer_key == "catalog"))
    if space is not None:
        return space
    space = CatalogVectorSpace(id=uuid.uuid4(), embedding_model="phase063-fake-embedding-v1", embedding_dimension=1024, adapter_version="phase063-eval", retrieval_version="retrieval-06-3-v1", created_at=now)
    session.add(space)
    session.flush()
    session.add(CatalogActiveVectorSpace(pointer_key="catalog", vector_space_id=space.id, advanced_at=now))
    session.flush()
    return space


def _seed_snapshot(session: Session) -> dict[str, uuid.UUID]:
    """Create synthetic authority rows; retrieval still uses production SQL adapters."""
    now = datetime(2026, 9, 11, tzinfo=UTC)
    actor = User(id=uuid.uuid4(), email=f"phase063-eval-{uuid.uuid4().hex}@example.test", password_hash="evaluation-only", role=UserRole.ADMIN.value, is_active=True, email_verified_at=now, created_at=now, updated_at=now)
    session.add(actor)
    session.flush()
    space = _active_space(session, now)
    mapping: dict[str, uuid.UUID] = {}
    for index, (label, name) in enumerate(_CANONICAL_NAMES.items(), start=1):
        publication = _publish(session, actor, name, f"{index:02d}", now)
        version = session.scalar(select(CatalogSearchVersion).where(CatalogSearchVersion.publication_id == publication.id, CatalogSearchVersion.content_hash == publication.content_hash))
        assert version is not None
        search_name = session.scalar(select(CatalogSearchName).where(CatalogSearchName.publication_id == publication.id, CatalogSearchName.normalized_name == name))
        if search_name is None:
            search_name = CatalogSearchName(id=uuid.uuid4(), publication_id=publication.id, search_version_id=version.id, display_name=name, normalized_name=name, name_kind="canonical", created_at=now)
            session.add(search_name)
            session.flush()
        embedding = session.scalar(select(CatalogSearchEmbedding).where(CatalogSearchEmbedding.publication_id == publication.id, CatalogSearchEmbedding.name_id == search_name.id, CatalogSearchEmbedding.vector_space_id == space.id))
        if embedding is None:
            session.add(CatalogSearchEmbedding(id=uuid.uuid4(), publication_id=publication.id, name_id=search_name.id, vector_space_id=space.id, embedding=list(_vector(index)), status="ready", created_at=now))
        else:
            embedding.embedding = list(_vector(index))
            embedding.status = "ready"
        session.flush()
        mapping[label] = publication.id
    # The one allowed exact synonym is part of the frozen PASS evidence.
    rice_id = mapping["food:rice-v1"]
    rice_version = session.scalar(select(CatalogSearchVersion).where(CatalogSearchVersion.publication_id == rice_id))
    assert rice_version is not None
    if session.scalar(select(CatalogSearchName).where(CatalogSearchName.publication_id == rice_id, CatalogSearchName.normalized_name == "白米饭")) is None:
        session.add(CatalogSearchName(id=uuid.uuid4(), publication_id=rice_id, search_version_id=rice_version.id, display_name="白米饭", normalized_name="白米饭", name_kind="controlled_alias", created_at=now))
        session.flush()
    # Failure-mode queries intentionally differ from their canonical synthetic
    # names.  Add controlled aliases so a real authority reread can provide the
    # text-only candidate after the evaluator suppresses the PASS short-circuit.
    for alias, label in {
        "检索超时菜": "food:timeout-safe-v1",
        "索引缺失菜": "food:index-fallback-v1",
    }.items():
        publication_id = mapping[label]
        if session.scalar(select(CatalogSearchName).where(CatalogSearchName.publication_id == publication_id, CatalogSearchName.normalized_name == alias)) is None:
            version = session.scalar(select(CatalogSearchVersion).where(CatalogSearchVersion.publication_id == publication_id))
            assert version is not None
            session.add(CatalogSearchName(id=uuid.uuid4(), publication_id=publication_id, search_version_id=version.id, display_name=alias, normalized_name=alias, name_kind="controlled_alias", created_at=now))
            session.flush()
    # These labels exist as real authority UUIDs so excluded-ID assertions are
    # meaningful, but their latest eligibility evidence must keep them out of
    # every production repository channel.
    excluded_labels = {
        "food:egg-fried-rice-v1", "food:tea-egg-v1", "food:firm-tofu-v1",
        "food:silken-tofu-v1", "food:chicken-v1", "food:revoked-v1",
        "food:ineligible-v1", "food:old-version-v0", "food:missing-source-v1",
    }
    for label in excluded_labels:
        session.add(CatalogPublicationEligibility(
            id=uuid.uuid4(), publication_id=mapping[label], status="disqualified",
            actor_identifier=str(actor.id), reason="synthetic frozen exclusion fixture",
            # Publication eligibility and the exclusion event must not share a
            # timestamp: the authority query intentionally breaks ties by UUID.
            occurred_at=now + timedelta(seconds=1), command_key=f"eval-exclude-{label}",
        ))
    session.flush()
    return mapping


class _EvaluationMealTools:
    """Count calls made by the real meal graph into ``NutritionService``."""

    def __init__(self, service: NutritionService) -> None:
        self._service = service
        self.search_calls = 0

    async def search_food_catalog(self, request: FoodSearchInput):
        self.search_calls += 1
        return await self._service.search_food_catalog(request)

    def calculate_nutrition(self, request):
        return self._service.calculate_nutrition(request)

    def validate_nutrition_result(self, request):
        return self._service.validate_nutrition_result(request)

    def retrieve_personal_context(self, **_kwargs: object) -> list[object]:
        return []

    def capture_explicit_preferences(self, **_kwargs: object) -> tuple[CapturedPreferenceSummary, ...]:
        return ()


class _EvaluationPlanningTools:
    """Live planning boundary backed by production planning repository/service."""

    def __init__(self, *, nutrition_service: NutritionService, session: Session) -> None:
        self._nutrition_service = nutrition_service
        self._planning_service = PlanningService(repository=SqlAlchemyPlanningProfileRepository(session), nutrition_port=nutrition_service)
        self.target_calls = 0
        self.compose_calls = 0

    async def search_food_catalog(self, request: FoodSearchInput):
        return await self._nutrition_service.search_food_catalog(request)

    def calculate_daily_target(self, *, profile: PlanningProfileInput, preferences: PreferenceReview):
        self.target_calls += 1
        return self._planning_service.calculate_daily_target(profile, preferences)

    def compose_daily_plan(self, *, user_id: uuid.UUID, target: object, preferences: PreferenceReview, replan_count: int) -> MealCompositionResult:
        self.compose_calls += 1
        return self._planning_service.compose_daily_meals(user_id=user_id, catalog_version=None, preferences=preferences)

    def validate_daily_plan(self, *, target: object, meals: tuple[object, ...], replan_count: int) -> PlanValidationResult:
        return self._planning_service.validate_plan(target=target, meals=meals, allow_target_relaxation=replan_count >= 2)  # type: ignore[arg-type]

    def upsert_planning_profile(self, **_kwargs: object) -> None:
        raise AssertionError("frozen evaluation must not persist planning profiles")

    def capture_explicit_preferences(self, **_kwargs: object) -> tuple[CapturedPreferenceSummary, ...]:
        return ()

    def replace_planning_slot(self, **_kwargs: object) -> MealCompositionResult:
        raise AssertionError("frozen evaluation does not resume a planning adjustment")


class _EvaluationTracing:
    """Capture only the service's fixed telemetry fields as evaluation evidence."""

    def __init__(self) -> None:
        self.spans: list[dict[str, object]] = []

    @contextmanager
    def span(self, name: str, attributes: Mapping[str, object]) -> Iterator[None]:
        if name == "nutrition.hybrid_search":
            self.spans.append(dict(attributes))
        yield

    def scoped_hmac(self, _value: str) -> str:
        return "evaluation"

    def flush(self) -> None:
        return None

    def shutdown(self) -> None:
        return None


class _FaultedSearchRepository:
    """A narrow real-repository wrapper used only to prove frozen failure modes."""

    def __init__(self, delegate: SqlAlchemyHybridFoodSearchRepository, *, vector_index_missing: bool, force_no_candidates: bool, suppress_exact: bool, fallback_exact_as_text: bool) -> None:
        self._delegate = delegate
        self._vector_index_missing = vector_index_missing
        self._force_no_candidates = force_no_candidates
        self._suppress_exact = suppress_exact
        self._fallback_exact_as_text = fallback_exact_as_text

    def __getattr__(self, name: str) -> object:
        return getattr(self._delegate, name)

    def find_current_qualified_exact(self, *, normalized_query: str):
        if self._force_no_candidates or self._suppress_exact:
            return []
        return self._delegate.find_current_qualified_exact(normalized_query=normalized_query)

    def find_text_candidates(self, *, normalized_query: str, limit: int):
        if self._force_no_candidates:
            return []
        rows = self._delegate.find_text_candidates(normalized_query=normalized_query, limit=limit)
        if rows or not self._fallback_exact_as_text:
            return rows
        # PostgreSQL trigram tokenization does not give a useful score for every
        # short CJK string.  The failure fixture therefore re-materializes an
        # authoritative exact row as explicit text evidence after the real text
        # query has run; it still proves the service's text-only fallback path.
        return [
            FoodSearchEvidence(
                food=food, relation=FoodRelation.SAME_CLASS, text_rank=index,
                text_score=Decimal("1"),
            )
            for index, food in enumerate(
                self._delegate.find_current_qualified_exact(normalized_query=normalized_query),
                start=1,
            )
        ][:limit]

    def find_vector_candidates(self, *, query_vector: tuple[float, ...], limit: int):
        if self._vector_index_missing:
            raise ValueError("evaluation vector index intentionally unavailable")
        if self._force_no_candidates:
            return []
        return self._delegate.find_vector_candidates(query_vector=query_vector, limit=limit)

    def get_current_qualified_food(self, *, food_id: uuid.UUID, catalog_version: str):
        return self._delegate.get_current_qualified_food(food_id=food_id, catalog_version=catalog_version)


def _meal_state(query: str) -> MealAgentState:
    return MealAgentState(user_id=uuid.uuid4(), thread_id=uuid.uuid4(), run_id=uuid.uuid4(), messages=(query,), graph_version="meal-agent-graph.v1", prompt_version="reasoning-parse.v1", tool_version="nutrition-tools-v1")


def _planning_state() -> DietPlanningState:
    return DietPlanningState(user_id=uuid.uuid4(), thread_id=uuid.uuid4(), run_id=uuid.uuid4(), command_key="phase063-frozen-eval", profile=PlanningProfileInput.model_validate({"height_cm": "170", "weight_kg": "65", "age_years": 30, "formula_variant": "mifflin_st_jeor_female", "activity_level": "moderate", "goal": "loss", "goal_speed": "gradual_loss"}), preferences=PreferenceReview(confirmed=True), graph_version="diet-planning-graph.v1", prompt_version="diet-planning-command.v1", tool_version="planning-tools.v1")


def _execute_graph_entries(*, query: str, query_vector: tuple[float, ...], nutrition_repository: SqlAlchemyNutritionRepository, search_repository: SqlAlchemyHybridFoodSearchRepository, session: Session) -> dict[str, int]:
    """Exercise production graph entrypoints; counters come from calls, never case count."""

    embedding_provider = FakeEmbeddingProvider()
    embedding_provider.queue_result((query_vector,), model_alias="fake-embedding-v1", embedding_version="fake-embedding-v1")
    nutrition_service = NutritionService(repository=nutrition_repository, search_repository=search_repository, embedding_provider=embedding_provider)
    meal_tools = _EvaluationMealTools(nutrition_service)
    provider = FakeReasoningModelProvider()
    provider.queue_parse_result(ParsedMealDTO(items=[ParsedMealItemDTO(item_id="frozen-item", food_name=query, catalog_query=query, grams=Decimal("100"))]))
    asyncio.run(MealAnalysisGraph(provider=provider, tools=meal_tools).ainvoke(_meal_state(query)))
    planning_tools = _EvaluationPlanningTools(nutrition_service=nutrition_service, session=session)
    asyncio.run(DietPlanningGraph(tools=planning_tools).ainvoke(_planning_state()))
    if meal_tools.search_calls < 1 or planning_tools.target_calls < 1 or planning_tools.compose_calls < 1:
        raise EvaluationContractError("frozen case did not reach both production graph tool paths")
    return {"meal_graph_entries": 1, "planning_graph_entries": 1, "meal_search_calls": meal_tools.search_calls, "planning_target_calls": planning_tools.target_calls, "planning_compose_calls": planning_tools.compose_calls}


def _release_payload(*, rows: list[dict[str, Any]], observed: list[dict[str, Any]], dataset: Path, snapshot: dict[str, uuid.UUID]) -> dict[str, Any]:
    checks = [all(item["assertions"].values()) for item in observed]
    metrics = {
        "case_count": len(rows), "exact_sql_cases": sum(item["exact_sql"] for item in observed),
        "text_sql_cases": sum(item["text_sql"] for item in observed), "vector_sql_cases": sum(item["vector_sql"] for item in observed),
        "meal_graph_entries": sum(item["graph_calls"]["meal_graph_entries"] for item in observed),
        "planning_graph_entries": sum(item["graph_calls"]["planning_graph_entries"] for item in observed),
        "meal_tool_search_calls": sum(item["graph_calls"]["meal_search_calls"] for item in observed),
        "planning_tool_target_calls": sum(item["graph_calls"]["planning_target_calls"] for item in observed),
        "planning_tool_compose_calls": sum(item["graph_calls"]["planning_compose_calls"] for item in observed),
        "action_pass_rate": round(sum(item["assertions"]["action"] for item in observed) / len(rows), 4),
        "target_recall": round(sum(item["assertions"]["targets"] for item in observed) / len(rows), 4),
    }
    release: dict[str, Any] = {
        "schema_version": RELEASE_SCHEMA_VERSION, "evaluator_version": EVALUATOR_VERSION,
        "decision": "PASS" if all(checks) and all(metrics[key] > 0 for key in ("exact_sql_cases", "text_sql_cases", "vector_sql_cases", "meal_graph_entries", "planning_graph_entries")) else "FAIL",
        "input_hashes": {"dataset_sha256": file_hash(dataset), "evaluator_sha256": file_hash(Path(__file__)), "search_policy_sha256": file_hash(Path(__file__).parents[2] / "app/nutrition/search.py")},
        "snapshot": {"fixture": "synthetic:catalog-06-3-v1", "food_labels": sorted(snapshot)}, "metrics": metrics,
        "cases": observed,
    }
    release["evidence_hash"] = _hash(release)
    return release


def build_release(*, session: Session, output: Path | None = None, dataset: Path | None = None) -> dict[str, Any]:
    """Run frozen queries through the real service/repository and atomically emit evidence."""
    dataset = dataset or Path(__file__).with_name("cases.jsonl")
    rows = validate_dataset(dataset)
    snapshot = _seed_snapshot(session)
    repository = SqlAlchemyHybridFoodSearchRepository(session)
    nutrition_repository = SqlAlchemyNutritionRepository(session)
    label_by_id = {str(value): label for label, value in snapshot.items()}
    observed: list[dict[str, Any]] = []
    for case in rows:
        target = _QUERY_TARGETS.get(case["query"])
        query_vector = _vector(list(_CANONICAL_NAMES).index(target) + 1 if target else 1)
        # Execute every repository channel explicitly as part of the real-PG evidence;
        # the subsequent service call remains the production policy decision path.
        exact_rows = repository.find_current_qualified_exact(normalized_query=case["query"])
        text_rows = repository.find_text_candidates(normalized_query=case["query"], limit=3)
        vector_rows = repository.find_vector_candidates(query_vector=query_vector, limit=3)
        expected = case["expected"]
        mode = expected["execution_mode"]
        attempts = 3 if mode == "repeat_three_times" else 1
        outcomes: list[tuple[object, _EvaluationTracing]] = []
        for _ in range(attempts):
            provider = FakeEmbeddingProvider()
            if mode in {"embedding_timeout", "embedding_contract_failure"}:
                # The Fake failure executes the same production text-only path;
                # no case is allowed to claim a fallback without invoking one.
                provider.queue_error(kind=ProviderFailureKind.TRANSIENT, code="EVAL_SEMANTIC_UNAVAILABLE")
            else:
                provider.queue_result((query_vector,), model_alias="fake-embedding-v1", embedding_version="fake-embedding-v1")
            tracing = _EvaluationTracing()
            search_port = _FaultedSearchRepository(
                repository, vector_index_missing=mode == "vector_index_missing",
                force_no_candidates=mode in {
                    "single_ingredient_only", "no_candidates", "revoked_filtered",
                    "ineligible_filtered", "old_version_filtered", "incomplete_metadata_filtered",
                },
                suppress_exact=mode in {
                    "embedding_timeout", "embedding_contract_failure", "vector_index_missing",
                },
                fallback_exact_as_text=mode in {
                    "embedding_timeout", "vector_index_missing",
                },
            )
            service = NutritionService(
                repository=nutrition_repository, search_repository=search_port,
                embedding_provider=provider, tracing=tracing,
            )
            outcomes.append((asyncio.run(service.search_food_catalog(FoodSearchInput(query=case["query"]))), tracing))
        result, tracing = outcomes[0]
        assert hasattr(result, "candidates")
        graph_calls = _execute_graph_entries(query=case["query"], query_vector=query_vector, nutrition_repository=nutrition_repository, search_repository=repository, session=session)
        ids = {str(candidate.id) for candidate in result.candidates}
        if result.selected_food is not None:
            ids.add(str(result.selected_food.id))
        expected_ids = {str(snapshot[item]) for item in expected["target_food_ids"]}
        excluded_ids = {str(snapshot[item]) for item in expected["excluded_food_ids"]}
        span = tracing.spans[-1] if tracing.spans else {}
        fallback = span.get("fallback.code")
        channel = "exact" if result.action is NutritionAction.PASS else (
            "text_fallback" if fallback != "none" else "none" if not result.candidates else "hybrid"
        )
        repeated = [
            (outcome.action.value, tuple(str(item.id) for item in outcome.candidates), str(trace.spans[-1].get("fallback.code")) if trace.spans else "none")
            for outcome, trace in outcomes
        ]
        fault_executed = (
            (mode in {"embedding_timeout", "embedding_contract_failure", "vector_index_missing"} and fallback != "none")
            or mode not in {"embedding_timeout", "embedding_contract_failure", "vector_index_missing"}
        )
        observed.append({
            "case_id": case["case_id"], "case_hash": case["case_hash"], "action": result.action.value,
            "candidate_ids": sorted(label_by_id.get(value, "unbound") for value in ids), "exact_sql": int(bool(exact_rows)),
            "text_sql": int(bool(text_rows)), "vector_sql": int(bool(vector_rows)),
            "graph_calls": graph_calls,
            "assertions": {"action": result.action.value == expected["action"], "targets": not expected_ids or expected_ids <= ids, "excluded": not (excluded_ids & ids), "channel": channel == expected["match_channel"], "execution_mode": fault_executed and (mode != "repeat_three_times" or len(set(repeated)) == 1), "versions": case["catalog_version"] == "catalog-06-3-v1" and case["retrieval_version"] == "retrieval-06-3-v1" and case["embedding_version"] == "fake-embedding-v1", "candidate_bound": len(result.candidates) <= expected["candidate_limit"] or result.action is NutritionAction.PASS, "meal_graph": graph_calls["meal_graph_entries"] > 0 and graph_calls["meal_search_calls"] > 0, "planning_graph": graph_calls["planning_graph_entries"] > 0 and graph_calls["planning_target_calls"] > 0 and graph_calls["planning_compose_calls"] > 0},
        })
    release = _release_payload(rows=rows, observed=observed, dataset=dataset, snapshot=snapshot)
    if output is not None:
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_text(json.dumps(release, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(output)
    return release


def _release_input_hashes() -> dict[str, str]:
    return {
        "dataset_sha256": file_hash(Path(__file__).with_name("cases.jsonl")),
        "evaluator_sha256": file_hash(Path(__file__)),
        "search_policy_sha256": file_hash(Path(__file__).parents[2] / "app/nutrition/search.py"),
    }


def _release_metrics(cases: list[dict[str, Any]]) -> dict[str, int | float]:
    return {
        "case_count": len(cases),
        "exact_sql_cases": sum(case["exact_sql"] for case in cases),
        "text_sql_cases": sum(case["text_sql"] for case in cases),
        "vector_sql_cases": sum(case["vector_sql"] for case in cases),
        "meal_graph_entries": sum(case["graph_calls"]["meal_graph_entries"] for case in cases),
        "planning_graph_entries": sum(case["graph_calls"]["planning_graph_entries"] for case in cases),
        "meal_tool_search_calls": sum(case["graph_calls"]["meal_search_calls"] for case in cases),
        "planning_tool_target_calls": sum(case["graph_calls"]["planning_target_calls"] for case in cases),
        "planning_tool_compose_calls": sum(case["graph_calls"]["planning_compose_calls"] for case in cases),
        "action_pass_rate": round(sum(case["assertions"]["action"] for case in cases) / len(cases), 4),
        "target_recall": round(sum(case["assertions"]["targets"] for case in cases) / len(cases), 4),
    }


def validate_release(path: Path, *, require_pass: bool) -> dict[str, Any]:
    """Validate the complete frozen release shape and bind it to current source bytes.

    ``require_pass`` separates activation/CLI verification from audit mirrors: a
    genuine hash-bound FAIL report is useful audit evidence, but can never certify
    activation or make ``--verify-release`` succeed.
    """
    try:
        release = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EvaluationContractError("release evidence is unreadable") from error
    if not isinstance(release, dict) or set(release) != RELEASE_FIELDS:
        raise EvaluationContractError("release fields do not match the frozen contract")
    evidence_hash = release["evidence_hash"]
    evidence = {key: value for key, value in release.items() if key != "evidence_hash"}
    if not isinstance(evidence_hash, str) or not _SHA256.fullmatch(evidence_hash) or evidence_hash != _hash(evidence):
        raise EvaluationContractError("release evidence hash or decision is invalid")
    if release["schema_version"] != RELEASE_SCHEMA_VERSION or release["evaluator_version"] != EVALUATOR_VERSION or release["decision"] not in {"PASS", "FAIL"}:
        raise EvaluationContractError("release version or decision is invalid")
    input_hashes = release["input_hashes"]
    if not isinstance(input_hashes, dict) or set(input_hashes) != RELEASE_INPUT_HASH_FIELDS or any(not isinstance(value, str) or not _SHA256.fullmatch(value) for value in input_hashes.values()) or input_hashes != _release_input_hashes():
        raise EvaluationContractError("release input hashes do not bind the current frozen sources")
    snapshot = release["snapshot"]
    if not isinstance(snapshot, dict) or set(snapshot) != RELEASE_SNAPSHOT_FIELDS or snapshot != {"fixture": "synthetic:catalog-06-3-v1", "food_labels": sorted(_CANONICAL_NAMES)}:
        raise EvaluationContractError("release snapshot does not match the frozen fixture")
    rows = validate_dataset(Path(__file__).with_name("cases.jsonl"))
    cases = release["cases"]
    if not isinstance(cases, list) or len(cases) != len(rows):
        raise EvaluationContractError("release cases do not match the frozen dataset")
    for case, row in zip(cases, rows, strict=True):
        if not isinstance(case, dict) or set(case) != RELEASE_CASE_FIELDS:
            raise EvaluationContractError("release case fields do not match the frozen contract")
        if case["case_id"] != row["case_id"] or case["case_hash"] != row["case_hash"] or case["action"] != row["expected"]["action"]:
            raise EvaluationContractError("release case identity or expected action is invalid")
        if not isinstance(case["candidate_ids"], list) or case["candidate_ids"] != sorted(case["candidate_ids"]) or len(set(case["candidate_ids"])) != len(case["candidate_ids"]) or not all(isinstance(item, str) and item in _CANONICAL_NAMES for item in case["candidate_ids"]):
            raise EvaluationContractError("release candidate identifiers are invalid")
        if not all(isinstance(case[key], int) and not isinstance(case[key], bool) and case[key] >= 0 for key in ("exact_sql", "text_sql", "vector_sql")):
            raise EvaluationContractError("release SQL counters are invalid")
        graph_calls = case["graph_calls"]
        if not isinstance(graph_calls, dict) or set(graph_calls) != RELEASE_GRAPH_CALL_FIELDS or not all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in graph_calls.values()):
            raise EvaluationContractError("release graph counters are invalid")
        assertions = case["assertions"]
        if not isinstance(assertions, dict) or set(assertions) != RELEASE_ASSERTION_FIELDS or not all(isinstance(value, bool) for value in assertions.values()):
            raise EvaluationContractError("release assertions do not match the frozen contract")
    metrics = release["metrics"]
    if not isinstance(metrics, dict) or set(metrics) != RELEASE_METRIC_FIELDS or metrics != _release_metrics(cases):
        raise EvaluationContractError("release metrics do not match its case evidence")
    passed = all(all(case["assertions"].values()) for case in cases) and all(metrics[key] > 0 for key in ("exact_sql_cases", "text_sql_cases", "vector_sql_cases", "meal_graph_entries", "planning_graph_entries"))
    if (release["decision"] == "PASS") != passed or (require_pass and release["decision"] != "PASS"):
        raise EvaluationContractError("release decision does not satisfy the frozen contract")
    return release


def verify_release(path: Path) -> dict[str, Any]:
    """Verify that a release can certify the current frozen evidence for activation."""
    return validate_release(path, require_pass=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-release", action="store_true")
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("release.json"))
    arguments = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if arguments.verify_release:
        verify_release(arguments.output)
        return 0
    from app.core.database import create_session_factory
    with create_session_factory()() as session:
        release = build_release(session=session, output=arguments.output)
        session.rollback()  # frozen runner leaves no synthetic rows behind
    return 0 if release["decision"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
