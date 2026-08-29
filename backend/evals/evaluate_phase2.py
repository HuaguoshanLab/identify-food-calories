"""Fail-closed Phase 2 evaluation evidence and release-input contracts.

The evaluator intentionally keeps frozen expectations out of the execution path.  A small,
versioned Fake Provider script supplies parser observations; the real graph and deterministic
PostgreSQL-backed tools then produce the evidence written to disk.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import uuid
from collections.abc import Iterable
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.agent.graph import GRAPH_VERSION, MealAnalysisGraph
from app.agent.service import AgentService, PROMPT_VERSION, TOOL_VERSION
from app.agent.state import AgentBudget, AgentRuntimeStatus, MealAgentState
from app.agent.tools import SessionNutritionToolAdapter
from app.core.config import Settings, validate_test_database_configuration
from app.providers.reasoning.dto import ParsedMealDTO, ParsedMealItemDTO, ProviderFailureKind
from app.providers.reasoning.fake import FakeReasoningModelProvider

if __package__ in {None, ""}:  # Support the documented ``python evals/evaluate_phase2.py`` form.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evals.validate_dataset import validate_dataset


EVALUATOR_VERSION = "phase2-code-eval.v1"
RUBRIC_VERSION = "phase02-rubric.v1"
REQUIRED_FAILURE_FIXTURES = frozenset(
    {
        "missing-nutritionist",
        "missing-food-data-steward",
        "duplicate-reviewer",
        "duplicate-pseudonym",
        "missing-human-score",
        "missing-judge-score",
        "dataset-hash-mismatch",
        "code-eval-hash-mismatch",
        "rubric-version-mismatch",
        "spearman-below-threshold",
        "critical-threshold-failure",
        "high-threshold-failure",
        "medium-average-failure",
        "medium-score-one",
        "promptfoo-missing-machine-output",
    }
)


class EvaluationContractError(ValueError):
    """A stable evaluator error that is safe to expose in CI."""


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_hash(path: Path) -> str:
    try:
        return _sha256_bytes(path.read_bytes())
    except OSError as error:
        raise EvaluationContractError(f"required evidence input is unavailable: {path.name}") from error


def _load_jsonl(dataset: Path) -> list[dict[str, Any]]:
    try:
        return [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line]
    except (OSError, json.JSONDecodeError) as error:
        raise EvaluationContractError("frozen dataset is unreadable") from error


def _dataset_contract(dataset: Path) -> list[dict[str, Any]]:
    validate_dataset(
        dataset,
        expected_count=24,
        expected_composition={"happy": 5, "missing_ambiguity": 5, "correction": 4, "persistence_isolation": 5, "validation_budget": 3, "adversarial": 2},
        required_happy_tags={"direct_grams", "exact_household_portion", "unique_alias", "multi_item", "beverage_and_condiment"},
    )
    return _load_jsonl(dataset)


def _implementation_hashes(root: Path) -> dict[str, str]:
    paths = {
        "evaluator": root / "evals/evaluate_phase2.py",
        "graph": root / "app/agent/graph.py",
        "provider": root / "app/providers/reasoning/fake.py",
        "tools": root / "app/agent/tools.py",
        "nutrition_service": root / "app/nutrition/service.py",
        "catalog": root / "app/nutrition/data/fdc-seed-v1.json",
        "state_schema": root / "app/agent/state.py",
    }
    return {name: file_hash(path) for name, path in paths.items()}


def _item(item_id: str, food_name: str, grams: str | None) -> ParsedMealItemDTO:
    return ParsedMealItemDTO(
        item_id=item_id,
        food_name=food_name,
        catalog_query=food_name,
        grams=Decimal(grams) if grams is not None else None,
    )


def _script_provider(case: dict[str, Any]) -> FakeReasoningModelProvider:
    """Provide an independent parser fixture, never reusing ``case.expected``.

    The script covers the frozen semantic tags with catalog aliases.  It is intentionally not a
    parser and never emits nutrition values, so every quantity and nutrition value still crosses
    the graph/tool boundary during the observed run.
    """

    provider = FakeReasoningModelProvider()
    tags = set(case["semantic_tags"])
    if tags == {"direct_grams"}:
        items = [_item("rice-1", "米饭", "150")]
    elif tags == {"exact_household_portion"}:
        # No catalog-controlled bowl conversion currently exists.  This must remain a real
        # interrupt rather than a provider-invented number.
        items = [_item("rice-1", "米饭", None)]
    elif tags == {"unique_alias"}:
        items = [_item("egg-1", "水煮蛋", "55")]
    elif tags == {"multi_item"}:
        items = [_item("rice-1", "米饭", "150"), _item("chicken-1", "鸡胸肉", "120"), _item("broccoli-1", "西兰花", "80")]
    elif tags == {"beverage_and_condiment"}:
        # The bounded FDC seed deliberately has neither product; observed failure is evidence,
        # not a reason to synthesize catalog facts.
        items = [_item("drink-1", "无糖豆浆", "250"), _item("sauce-1", "酱油", "10")]
    elif tags & {"missing_grams", "cooking_state", "edible_portion", "ambiguous_candidate"}:
        items = [_item("rice-1", "米饭", None)]
    elif "out_of_catalog" in tags:
        items = [_item("unknown-1", "火星菜", "80"), _item("rice-1", "米饭", "100")]
    elif tags & {"negative_grams", "tool_failure", "model_call_limit", "prompt_injection", "medical_boundary"}:
        provider.queue_parse_error(kind=ProviderFailureKind.PERMANENT, code="FAKE_SAFETY_OR_FAILURE")
        return provider
    else:
        items = [_item("rice-1", "米饭", "100")]
    provider.queue_parse_result(ParsedMealDTO(items=items))
    return provider


class _ObservedTools(SessionNutritionToolAdapter):
    """Record only tool names/actions, leaving database work to the real adapter."""

    def __init__(self, *, session_factory: Any) -> None:
        super().__init__(session_factory=session_factory)
        self.trace: list[str] = []

    def search_food_catalog(self, request: Any) -> Any:
        result = super().search_food_catalog(request)
        self.trace.append(f"search_food_catalog:{result.action.value}")
        return result

    def calculate_nutrition(self, request: Any) -> Any:
        result = super().calculate_nutrition(request)
        self.trace.append(f"calculate_nutrition:{result.action.value}")
        return result

    def validate_nutrition_result(self, request: Any) -> Any:
        result = super().validate_nutrition_result(request)
        self.trace.append(f"validate_nutrition_result:{result.action.value}")
        return result


def _safe_report(state: MealAgentState) -> dict[str, object] | None:
    if state.report is None:
        return None
    # The report is already the public graph projection.  Retain only its safe structure.
    return state.report


async def _run_case(
    *, case: dict[str, Any], session_factory: Any, checkpointer: object
) -> dict[str, object]:
    provider = _script_provider(case)
    tools = _ObservedTools(session_factory=session_factory)
    graph = MealAnalysisGraph(provider=provider, tools=tools)
    user_id, thread_id, run_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    tags = set(case["semantic_tags"])
    initial = MealAgentState(
        user_id=user_id,
        thread_id=thread_id,
        run_id=run_id,
        messages=(case["input"]["message"],),
        graph_version=GRAPH_VERSION,
        prompt_version=PROMPT_VERSION,
        tool_version=TOOL_VERSION,
        budget=AgentBudget(model_calls=4) if "model_call_limit" in tags else AgentBudget(),
    )
    state = await graph.ainvoke(initial)
    await AgentService._persist_checkpoint(checkpointer=checkpointer, state=state)
    reopened = await AgentService._load_checkpoint(checkpointer=checkpointer, thread_id=thread_id)
    if reopened is None:
        raise EvaluationContractError("real checkpointer did not return persisted state")

    resume = case["input"].get("resume_payload")
    if isinstance(resume, dict) and state.status in {AgentRuntimeStatus.WAITING_INPUT, AgentRuntimeStatus.COMPLETED}:
        # Resume only after a durable read.  The response is graph-observed, not an expected
        # fixture copied into evidence.
        state = await graph.ainvoke(reopened, resume=resume)
        await AgentService._persist_checkpoint(checkpointer=checkpointer, state=state)
        reopened = await AgentService._load_checkpoint(checkpointer=checkpointer, thread_id=thread_id)
        if reopened is None:
            raise EvaluationContractError("resumed checkpoint could not be reopened")

    event_types = ["running"]
    if state.status is AgentRuntimeStatus.WAITING_INPUT:
        event_types.append("waiting_input")
    elif state.status is AgentRuntimeStatus.COMPLETED:
        event_types.append("completed")
    else:
        event_types.append("failed")
    state_json = state.model_dump(mode="json")
    forbidden = {
        "provider_nutrition_value": not any("provider" in key for key in state_json),
        "chain_of_thought": "chain_of_thought" not in json.dumps(state_json, ensure_ascii=False),
        "no_raw_input_persisted": case["input"]["message"] not in json.dumps(state_json, ensure_ascii=False),
    }
    observed = {
        "state": state.status.value,
        "trace": ["fake_provider:parse_meal", *tools.trace],
        "report": _safe_report(state),
        "events": event_types,
        "forbidden_outcomes": forbidden,
        "provider_calls": [call.operation for call in provider.calls],
        "checkpoint_reopened": reopened.thread_id == thread_id and reopened.run_id == run_id,
        "state_digest": _sha256_bytes(_canonical_json(state_json)),
    }
    critical = {
        "checkpoint_reopened": bool(observed["checkpoint_reopened"]),
        "deterministic_tools_only": all(not name.startswith("provider_nutrition") for name in tools.trace),
        "no_chain_of_thought": bool(forbidden["chain_of_thought"]),
    }
    high = {
        "bounded_provider_calls": len(provider.calls) <= 4,
        "safe_event_sequence": event_types[-1] in {"waiting_input", "completed", "failed"},
        "no_invented_household_grams": not ("exact_household_portion" in tags and state.status is AgentRuntimeStatus.COMPLETED),
    }
    return {
        "case_id": case["case_id"],
        "case_hash": case["case_hash"],
        "observed": observed,
        "assertions": {"critical": critical, "high": high},
        "execution": {
            "runner": "fake-provider->meal-graph->postgres-tools->postgres-checkpointer",
            "thread_id_digest": _sha256_bytes(str(thread_id).encode()),
            "run_id_digest": _sha256_bytes(str(run_id).encode()),
        },
    }


def _percent(values: Iterable[bool]) -> float:
    actual = list(values)
    return round(100 * sum(actual) / len(actual), 2) if actual else 0.0


def run_code_eval(*, dataset: Path, output: Path) -> dict[str, object]:
    records = _dataset_contract(dataset)
    root = Path(__file__).resolve().parents[1]
    if os.environ.get("APP_ENV") != "test":
        raise EvaluationContractError("run-code-eval requires APP_ENV=test through tests/run_pg.py")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    database_url = validate_test_database_configuration(settings)
    subprocess.run([sys.executable, "scripts/run_initialized_app.py", "--prepare-only"], cwd=root, check=True)
    engine = create_engine(database_url, pool_pre_ping=True)
    factory = sessionmaker(engine, expire_on_commit=False)
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    conninfo = make_url(database_url).set(drivername="postgresql").render_as_string(hide_password=False)

    async def execute() -> list[dict[str, object]]:
        serde = JsonPlusSerializer(pickle_fallback=False, allowed_msgpack_modules=None)
        async with AsyncPostgresSaver.from_conn_string(conninfo, serde=serde) as saver:
            return [await _run_case(case=record, session_factory=factory, checkpointer=saver) for record in records]

    try:
        cases = asyncio.run(execute())
    finally:
        engine.dispose()
    result: dict[str, object] = {
        "schema_version": EVALUATOR_VERSION,
        "rubric_version": RUBRIC_VERSION,
        "dataset_hash": file_hash(dataset),
        "implementation_hashes": _implementation_hashes(root),
        "case_count": len(cases),
        "cases": cases,
        "summary": {
            "critical_pass_percent": _percent(value for row in cases for value in row["assertions"]["critical"].values()),  # type: ignore[index]
            "high_pass_percent": _percent(value for row in cases for value in row["assertions"]["high"].values()),  # type: ignore[index]
        },
    }
    result["evidence_hash"] = _sha256_bytes(_canonical_json(result))
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def verify_code_eval(*, dataset: Path, result: Path) -> dict[str, object]:
    records = _dataset_contract(dataset)
    try:
        payload = json.loads(result.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EvaluationContractError("code eval result is unreadable") from error
    if not isinstance(payload, dict) or payload.get("schema_version") != EVALUATOR_VERSION:
        raise EvaluationContractError("code eval schema version is invalid")
    cases = payload.get("cases")
    if isinstance(cases, list):
        for row in cases:
            execution = row.get("execution") if isinstance(row, dict) else None
            if not isinstance(execution, dict) or execution.get("runner") != "fake-provider->meal-graph->postgres-tools->postgres-checkpointer":
                raise EvaluationContractError("code eval execution evidence is missing")
    if payload.get("dataset_hash") != file_hash(dataset):
        raise EvaluationContractError("code eval dataset hash is stale")
    evidence_hash = payload.pop("evidence_hash", None)
    if not isinstance(evidence_hash, str) or evidence_hash != _sha256_bytes(_canonical_json(payload)):
        raise EvaluationContractError("code eval evidence hash is invalid")
    expected_ids = [record["case_id"] for record in records]
    if not isinstance(cases, list) or [row.get("case_id") for row in cases if isinstance(row, dict)] != expected_ids:
        raise EvaluationContractError("code eval case set is incomplete or reordered")
    required_hashes = _implementation_hashes(Path(__file__).resolve().parents[1])
    if payload.get("implementation_hashes") != required_hashes:
        raise EvaluationContractError("code eval implementation hash is stale")
    for row in cases:
        if not isinstance(row, dict) or not isinstance(row.get("observed"), dict):
            raise EvaluationContractError("code eval observed result is missing")
        observed = row["observed"]
        required = {"state", "trace", "report", "events", "forbidden_outcomes", "provider_calls", "checkpoint_reopened", "state_digest"}
        if not required <= set(observed):
            raise EvaluationContractError("code eval observed execution evidence is incomplete")
    payload["evidence_hash"] = evidence_hash
    return payload


def load_failure_fixtures(path: Path) -> list[dict[str, object]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EvaluationContractError("release failure fixtures are unreadable") from error
    fixtures = payload.get("fixtures") if isinstance(payload, dict) else None
    if not isinstance(fixtures, list) or not all(isinstance(item, dict) for item in fixtures):
        raise EvaluationContractError("release failure fixtures have invalid structure")
    return fixtures


def _validate_promptfoo_config(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for required in ("phase02-001", "phase02-012", "repeat: 3", "--no-cache", "network_failure", "product_failure"):
        if required not in text:
            raise EvaluationContractError("promptfoo config lacks fixed release contract")
    if text.count("case_id:") != 12:
        raise EvaluationContractError("promptfoo config must contain exactly twelve fixed cases")


def validate_contracts(*, dataset: Path, code_eval: Path, signoff_schema: Path, promptfoo_config: Path) -> None:
    verify_code_eval(dataset=dataset, result=code_eval)
    try:
        schema = json.loads(signoff_schema.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EvaluationContractError("expert signoff schema is unreadable") from error
    serialized = json.dumps(schema, ensure_ascii=False, sort_keys=True)
    for term in ("nutritionist", "food_composition_data_steward", "pseudonym", "dataset_hash", "code_eval_hash", "human_score", "judge_score"):
        if term not in serialized:
            raise EvaluationContractError("expert signoff schema lacks mandatory release field")
    _validate_promptfoo_config(promptfoo_config)


def self_test(*, fixtures: Path) -> None:
    known = load_failure_fixtures(fixtures)
    actual = {str(item.get("id")) for item in known}
    missing = REQUIRED_FAILURE_FIXTURES - actual
    if missing:
        raise EvaluationContractError("release failure fixture coverage is incomplete")
    for fixture in known:
        if fixture.get("expected") != "reject":
            raise EvaluationContractError("failure fixture must be fail-closed")


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EvaluationContractError(f"{label} is unreadable") from error
    if not isinstance(payload, dict):
        raise EvaluationContractError(f"{label} must be an object")
    return payload


def validate_signoff(*, dataset: Path, code_eval: Path, signoff: Path) -> dict[str, Any]:
    records = _dataset_contract(dataset)
    verify_code_eval(dataset=dataset, result=code_eval)
    payload = _read_json(signoff, label="expert signoff")
    if payload.get("schema_version") != "expert-signoff.v1" or payload.get("rubric_version") != RUBRIC_VERSION:
        raise EvaluationContractError("expert signoff schema or rubric version is invalid")
    if payload.get("dataset_hash") != file_hash(dataset) or payload.get("code_eval_hash") != file_hash(code_eval):
        raise EvaluationContractError("expert signoff hash binding is stale")
    reviews = payload.get("reviews")
    judges = payload.get("judge_scores")
    if not isinstance(reviews, list) or not isinstance(judges, list):
        raise EvaluationContractError("expert signoff reviews or judge scores are missing")
    case_ids = {record["case_id"] for record in records}
    required_roles = {"nutritionist", "food_composition_data_steward"}
    by_case: dict[str, list[dict[str, Any]]] = {case_id: [] for case_id in case_ids}
    global_pseudonyms: set[str] = set()
    for review in reviews:
        if not isinstance(review, dict):
            raise EvaluationContractError("expert signoff review is invalid")
        case_id, role, pseudonym = review.get("case_id"), review.get("role"), review.get("pseudonym")
        if case_id not in by_case or role not in required_roles | {"product", "privacy"} or not isinstance(pseudonym, str):
            raise EvaluationContractError("expert signoff reviewer identity is invalid")
        if review.get("rubric_version") != RUBRIC_VERSION or review.get("dataset_hash") != file_hash(dataset) or review.get("code_eval_hash") != file_hash(code_eval):
            raise EvaluationContractError("expert signoff review hash binding is invalid")
        confirmations = review.get("confirmations")
        if not isinstance(confirmations, dict) or set(confirmations) != {"food_code", "blocking_fields", "household_portion_auditability", "authoritative_values", "hard_validation"} or not all(value is True for value in confirmations.values()):
            raise EvaluationContractError("expert signoff confirmations are incomplete")
        if pseudonym in global_pseudonyms:
            raise EvaluationContractError("expert signoff pseudonym must identify one real reviewer")
        global_pseudonyms.add(pseudonym)
        by_case[case_id].append(review)
    medium_case_ids = {record["case_id"] for record in records if record["category"] == "missing_ambiguity"}
    human_scores: dict[str, int] = {}
    for case_id, case_reviews in by_case.items():
        roles = {str(review["role"]) for review in case_reviews}
        if not required_roles <= roles:
            raise EvaluationContractError("each case requires nutritionist and food composition data steward")
        if len({str(review["pseudonym"]) for review in case_reviews}) != len(case_reviews):
            raise EvaluationContractError("one reviewer cannot satisfy multiple case roles")
        if case_id in medium_case_ids:
            scores: list[int] = []
            for review in case_reviews:
                score = review.get("medium_human_score")
                if isinstance(score, int):
                    scores.append(score)
            if not scores or any(score < 1 or score > 5 for score in scores):
                raise EvaluationContractError("medium case is missing a human 1-5 score")
            human_scores[case_id] = scores[0]
    judge_scores: dict[str, int] = {}
    for judge in judges:
        if not isinstance(judge, dict) or judge.get("case_id") not in medium_case_ids:
            raise EvaluationContractError("judge score is not bound to a medium case")
        case_id = str(judge["case_id"])
        score = judge.get("score")
        if case_id in judge_scores or not isinstance(score, int) or score < 1 or score > 5:
            raise EvaluationContractError("judge score is invalid")
        if judge.get("rubric_version") != RUBRIC_VERSION or judge.get("dataset_hash") != file_hash(dataset) or judge.get("code_eval_hash") != file_hash(code_eval):
            raise EvaluationContractError("judge score hash binding is invalid")
        judge_scores[case_id] = score
    if set(judge_scores) != medium_case_ids or set(human_scores) != medium_case_ids:
        raise EvaluationContractError("every medium case requires paired human and judge scores")
    return payload


def _rank(values: list[int]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(ordered):
        end = position
        while end + 1 < len(ordered) and ordered[end + 1][1] == ordered[position][1]:
            end += 1
        average = (position + 1 + end + 1) / 2
        for index in range(position, end + 1):
            ranks[ordered[index][0]] = average
        position = end + 1
    return ranks


def spearman(human: list[int], judge: list[int]) -> float:
    if len(human) < 2 or len(human) != len(judge):
        raise EvaluationContractError("Spearman requires paired per-case scores")
    left, right = _rank(human), _rank(judge)
    mean_left, mean_right = sum(left) / len(left), sum(right) / len(right)
    numerator = sum((a - mean_left) * (b - mean_right) for a, b in zip(left, right, strict=True))
    left_norm = sum((a - mean_left) ** 2 for a in left) ** 0.5
    right_norm = sum((b - mean_right) ** 2 for b in right) ** 0.5
    if not left_norm or not right_norm:
        raise EvaluationContractError("Spearman scores must not be constant")
    return round(numerator / (left_norm * right_norm), 6)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run-code-eval")
    run.add_argument("--dataset", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    verify = commands.add_parser("verify-code-eval")
    verify.add_argument("--dataset", type=Path, required=True)
    verify.add_argument("--result", type=Path, required=True)
    self_command = commands.add_parser("self-test")
    self_command.add_argument("--fixtures", type=Path, required=True)
    contract = commands.add_parser("validate-contracts")
    contract.add_argument("--dataset", type=Path, required=True)
    contract.add_argument("--code-eval", type=Path, required=True)
    contract.add_argument("--signoff-schema", type=Path, required=True)
    contract.add_argument("--promptfoo-config", type=Path, required=True)
    signoff = commands.add_parser("validate-signoff")
    signoff.add_argument("--dataset", type=Path, required=True)
    signoff.add_argument("--code-eval", type=Path, required=True)
    signoff.add_argument("--signoff", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if arguments.command == "run-code-eval":
            run_code_eval(dataset=arguments.dataset, output=arguments.output)
        elif arguments.command == "verify-code-eval":
            verify_code_eval(dataset=arguments.dataset, result=arguments.result)
        elif arguments.command == "self-test":
            self_test(fixtures=arguments.fixtures)
        elif arguments.command == "validate-signoff":
            validate_signoff(dataset=arguments.dataset, code_eval=arguments.code_eval, signoff=arguments.signoff)
        else:
            validate_contracts(dataset=arguments.dataset, code_eval=arguments.code_eval, signoff_schema=arguments.signoff_schema, promptfoo_config=arguments.promptfoo_config)
    except EvaluationContractError as error:
        print(f"evaluation contract rejected: {error}", file=sys.stderr)
        return 2
    print("evaluation contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
