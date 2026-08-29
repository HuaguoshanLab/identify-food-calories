"""Run the authorized 36-call Phase 2 Judge release with fail-closed accounting."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from app.core.config import Settings


CASES = tuple(f"phase02-{number:03d}" for number in range(1, 13))
MEDIUM_CASES = frozenset(f"phase02-{number:03d}" for number in range(6, 11))
REPEAT = 3
MAX_CALLS = len(CASES) * REPEAT
MAX_OUTPUT_TOKENS = 512
REQUEST_OVERHEAD_TOKEN_CAP = 1024
BUDGET_CNY = Decimal("0.20")
FX_CNY_PER_USD_CEILING = Decimal("8")
REQUIRED_CONFIRMATIONS = (
    "food_code",
    "blocking_fields",
    "household_portion_auditability",
    "authoritative_values",
    "hard_validation",
)


@dataclass(frozen=True)
class CallEvidence:
    case_id: str
    repeat_index: int
    status: str
    failure_category: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    cost_usd: str | None
    cost_cny_at_ceiling: str | None
    judge_score: int | None
    promptfoo_exit_code: int | None
    failure_stage: str | None
    parse_stage: str | None
    output_shape: dict[str, Any] | None


class OutputParseError(ValueError):
    """A fail-closed parsing error whose stage is safe to persist as evidence."""

    def __init__(self, stage: str) -> None:
        super().__init__(stage)
        self.stage = stage


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=Path("evals/promptfooconfig.yaml")
    )
    parser.add_argument(
        "--dataset", type=Path, default=Path("evals/phase02-cases.jsonl")
    )
    parser.add_argument(
        "--code-eval", type=Path, default=Path("evals/phase2-code-eval.json")
    )
    parser.add_argument(
        "--template", type=Path, default=Path("evals/expert-signoff-phase2.template.md")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("evals/promptfoo-release-phase2.json")
    )
    parser.add_argument(
        "--signoff-output", type=Path, default=Path("evals/expert-signoff-phase2.json")
    )
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()

    settings = Settings()
    _validate_settings(settings)
    config_bytes = args.config.read_bytes()
    _validate_config(config_bytes)
    dataset_hash = _sha256(args.dataset.read_bytes())
    code_eval_hash = _sha256(args.code_eval.read_bytes())
    input_price = _decimal(settings.deepseek_input_usd_per_m)
    output_price = _decimal(settings.deepseek_output_usd_per_m)
    input_cap = len(config_bytes) + REQUEST_OVERHEAD_TOKEN_CAP
    maximum_per_call_usd = (
        Decimal(input_cap) * input_price + Decimal(MAX_OUTPUT_TOKENS) * output_price
    ) / Decimal("1000000")
    maximum_total_cny = maximum_per_call_usd * MAX_CALLS * FX_CNY_PER_USD_CEILING
    common = {
        "schema_version": "phase2-promptfoo-release.v1",
        "release_eligible": False,
        "model": settings.deepseek_model,
        "calls_authorized": MAX_CALLS,
        "max_concurrency": 1,
        "cache": "disabled",
        "max_retries": 0,
        "dataset_hash": dataset_hash,
        "code_eval_hash": code_eval_hash,
        "config_hash": _sha256(config_bytes),
        "price_snapshot_version": settings.deepseek_price_snapshot_version,
        "price_snapshot_fingerprint": _sha256(
            f"{settings.deepseek_price_snapshot_version}:{input_price}:{output_price}".encode()
        ),
        "budget_cny": str(BUDGET_CNY),
        "fx_cny_per_usd_ceiling": str(FX_CNY_PER_USD_CEILING),
        "input_token_cap_per_call": input_cap,
        "output_token_cap_per_call": MAX_OUTPUT_TOKENS,
        "maximum_total_cny_at_caps": str(maximum_total_cny),
    }
    if maximum_total_cny > BUDGET_CNY:
        _write(
            args.output,
            {
                **common,
                "status": "blocked_budget_preflight",
                "calls_attempted": 0,
                "calls_completed": 0,
                "calls": [],
            },
        )
        return 2
    if args.preflight_only:
        _write(
            args.output,
            {
                **common,
                "status": "preflight_passed",
                "calls_attempted": 0,
                "calls_completed": 0,
                "calls": [],
            },
        )
        return 0

    calls: list[CallEvidence] = []
    spent_cny = Decimal("0")
    with tempfile.TemporaryDirectory(prefix="phase2-promptfoo-release-") as directory:
        temporary = Path(directory)
        for repeat_index in range(REPEAT):
            for case_index, case_id in enumerate(CASES):
                if (
                    spent_cny + maximum_per_call_usd * FX_CNY_PER_USD_CEILING
                    > BUDGET_CNY
                ):
                    calls.append(
                        CallEvidence(
                            case_id,
                            repeat_index + 1,
                            "blocked",
                            "budget",
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            None,
                            "budget",
                            None,
                            None,
                        )
                    )
                    break
                raw_output = temporary / f"{repeat_index}-{case_index}.json"
                result = subprocess.run(
                    [
                        "../frontend/node_modules/.bin/promptfoo",
                        "eval",
                        "-c",
                        str(args.config),
                        "--env-file",
                        ".env",
                        "--filter-range",
                        f"{case_index}:{case_index + 1}",
                        "--repeat",
                        "1",
                        "--max-concurrency",
                        "1",
                        "--no-cache",
                        "--no-write",
                        "--no-share",
                        "--no-table",
                        "--output",
                        str(raw_output),
                    ],
                    cwd=Path.cwd(),
                    env={
                        "PATH": os.environ.get("PATH", ""),
                        "HOME": os.environ.get("HOME", ""),
                        "CI": "true",
                        "PROMPTFOO_DISABLE_UPDATE": "true",
                        "NO_COLOR": "1",
                    },
                    capture_output=True,
                    text=True,
                    check=False,
                )
                evidence = _call_evidence(
                    case_id,
                    repeat_index + 1,
                    result,
                    raw_output,
                    input_price,
                    output_price,
                )
                calls.append(evidence)
                if evidence.cost_cny_at_ceiling is not None:
                    spent_cny += Decimal(evidence.cost_cny_at_ceiling)
                if evidence.status != "completed" or spent_cny > BUDGET_CNY:
                    break
            if (
                len(calls) != (repeat_index + 1) * len(CASES)
                or calls[-1].status != "completed"
            ):
                break

    score_sets: dict[str, list[int]] = defaultdict(list)
    for call in calls:
        if call.case_id in MEDIUM_CASES and call.judge_score is not None:
            score_sets[call.case_id].append(call.judge_score)
    judge_scores = {
        case_id: scores[0]
        for case_id, scores in score_sets.items()
        if len(scores) == REPEAT and len(set(scores)) == 1
    }
    completed = len(calls) == MAX_CALLS and all(
        call.status == "completed" for call in calls
    )
    scores_complete = set(judge_scores) == MEDIUM_CASES
    cost_known = all(call.cost_cny_at_ceiling is not None for call in calls)
    status = "completed" if completed and scores_complete else "stopped"
    document = {
        **common,
        "status": status,
        "calls_attempted": len(calls),
        "calls_completed": sum(call.status == "completed" for call in calls),
        "actual_cost_cny_at_ceiling": str(spent_cny) if cost_known else None,
        "cost_accounting": "usage_accounted"
        if cost_known
        else "unknown_after_failed_call",
        "judge_scores": judge_scores,
        "calls": [asdict(call) for call in calls],
        "generated_at": datetime.now(UTC).isoformat(),
    }
    _write(args.output, document)
    if status != "completed":
        return 1
    _materialize_signoff(
        template=args.template,
        output=args.signoff_output,
        dataset_hash=dataset_hash,
        code_eval_hash=code_eval_hash,
        judge_scores=judge_scores,
    )
    return 0


def _validate_settings(settings: Settings) -> None:
    if (
        settings.deepseek_api_key is None
        or not settings.deepseek_api_key.get_secret_value().strip()
    ):
        raise ValueError("DEEPSEEK_API_KEY is required")
    if settings.deepseek_model != "deepseek-v4-flash":
        raise ValueError("release requires pinned deepseek-v4-flash")
    if not settings.deepseek_price_snapshot_version:
        raise ValueError("DEEPSEEK_PRICE_SNAPSHOT_VERSION is required")
    _decimal(settings.deepseek_input_usd_per_m)
    _decimal(settings.deepseek_output_usd_per_m)


def _validate_config(config_bytes: bytes) -> None:
    text = config_bytes.decode("utf-8")
    required = (
        "openai:chat:deepseek-v4-flash",
        "maxRetries: 0",
        "max_tokens: 512",
        "repeat: 3",
        "maxConcurrency: 1",
        "cache: false",
    )
    if any(value not in text for value in required):
        raise ValueError("release config is missing a hard safety setting")
    if len(re.findall(r"case_id:\s*phase02-\d+", text)) != len(CASES):
        raise ValueError("release config must contain exactly twelve fixed cases")


def _call_evidence(
    case_id: str,
    repeat_index: int,
    result: subprocess.CompletedProcess[str],
    raw_output: Path,
    input_price: Decimal,
    output_price: Decimal,
) -> CallEvidence:
    if result.returncode != 0 or not raw_output.exists():
        output = result.stdout + result.stderr
        return CallEvidence(
            case_id,
            repeat_index,
            "failed",
            _failure_category(output),
            None,
            None,
            None,
            None,
            None,
            None,
            result.returncode,
            _failure_stage(output),
            None,
            None,
        )
    document: Any = None
    try:
        document = json.loads(raw_output.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return CallEvidence(
            case_id,
            repeat_index,
            "failed",
            "product_failure",
            None,
            None,
            None,
            None,
            None,
            None,
            result.returncode,
            "output_parse",
            "document_json",
            None,
        )
    shape = _safe_output_shape(document)
    try:
        row = _result_row(document, case_id)
        response = _response(row)
        usage = _usage(row, response)
        prompt_tokens = _usage_int(usage.get("prompt"))
        completion_tokens = _usage_int(usage.get("completion"))
        total_tokens = _usage_int(usage.get("total"), prompt_tokens + completion_tokens)
        cost_usd = (
            Decimal(prompt_tokens) * input_price
            + Decimal(completion_tokens) * output_price
        ) / Decimal("1000000")
        cost_cny = cost_usd * FX_CNY_PER_USD_CEILING
    except OutputParseError as error:
        return CallEvidence(
            case_id,
            repeat_index,
            "failed",
            "product_failure",
            None,
            None,
            None,
            None,
            None,
            None,
            result.returncode,
            "output_parse",
            error.stage,
            shape,
        )
    except (TypeError, ValueError, InvalidOperation):
        return CallEvidence(
            case_id,
            repeat_index,
            "failed",
            "product_failure",
            None,
            None,
            None,
            None,
            None,
            None,
            result.returncode,
            "output_parse",
            "cost",
            shape,
        )
    try:
        score = _judge_score(_response_output(row, response))
    except OutputParseError as error:
        return CallEvidence(
            case_id,
            repeat_index,
            "failed",
            "product_failure",
            prompt_tokens,
            completion_tokens,
            total_tokens,
            str(cost_usd),
            str(cost_cny),
            None,
            result.returncode,
            "output_parse",
            error.stage,
            shape,
        )
    return CallEvidence(
        case_id,
        repeat_index,
        "completed",
        None,
        prompt_tokens,
        completion_tokens,
        total_tokens,
        str(cost_usd),
        str(cost_cny),
        score,
        result.returncode,
        None,
        None,
        None,
    )


def _result_row(document: Any, expected_case_id: str) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise OutputParseError("result_shape")
    summary = document.get("results")
    rows = summary.get("results") if isinstance(summary, dict) else summary
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise OutputParseError("result_shape")
    row = rows[0]
    variables = row.get("vars")
    if not isinstance(variables, dict) or variables.get("case_id") != expected_case_id:
        raise OutputParseError("target_case")
    return row


def _response(row: dict[str, Any]) -> dict[str, Any]:
    response = row.get("response") or row.get("providerResponse")
    if not isinstance(response, dict):
        raise OutputParseError("response")
    return response


def _usage(row: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    usage = response.get("tokenUsage") or row.get("tokenUsage")
    if not isinstance(usage, dict):
        raise OutputParseError("usage")
    return usage


def _response_output(row: dict[str, Any], response: dict[str, Any]) -> Any:
    value = response.get("output") if "output" in response else row.get("output")
    if value is None:
        raise OutputParseError("judge_score")
    return value


def _safe_output_shape(document: Any) -> dict[str, Any]:
    """Return structure only; never retain prompts, responses, variables, or values."""

    shape: dict[str, Any] = {"document_type": _shape_type(document)}
    if not isinstance(document, dict):
        return shape
    shape["document_safe_keys"] = _safe_keys(document)
    results = document.get("results")
    shape["results_type"] = _shape_type(results)
    if isinstance(results, list):
        shape["results_length"] = len(results)
    elif isinstance(results, dict):
        shape["results_safe_keys"] = _safe_keys(results)
        nested = results.get("results")
        shape["nested_results_type"] = _shape_type(nested)
        if isinstance(nested, list):
            shape["nested_results_length"] = len(nested)
    return shape


def _shape_type(value: Any) -> str:
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if value is None:
        return "null"
    return type(value).__name__


def _safe_keys(value: dict[str, Any]) -> list[str]:
    sensitive = {
        "config",
        "metadata",
        "output",
        "prompt",
        "providerresponse",
        "response",
        "text",
        "traces",
        "value",
        "vars",
    }
    return sorted(key for key in value if key.lower() not in sensitive)


def _materialize_signoff(
    *,
    template: Path,
    output: Path,
    dataset_hash: str,
    code_eval_hash: str,
    judge_scores: dict[str, int],
) -> None:
    rows = [
        line
        for line in template.read_text(encoding="utf-8").splitlines()
        if line.startswith("| phase02-")
    ]
    if len(rows) != 24:
        raise ValueError("expert template must contain exactly 24 case rows")
    reviews: list[dict[str, Any]] = []
    expected_fields = "; ".join(f"{name}=true" for name in REQUIRED_CONFIRMATIONS)
    for row in rows:
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        case_id, _, yu_text, chen_text, medium_text = cells
        if not yu_text.startswith("于：") or not chen_text.startswith("陈："):
            raise ValueError(
                f"expert template has ambiguous reviewer columns for {case_id}"
            )
        if (
            yu_text.removeprefix("于：") != expected_fields
            or chen_text.removeprefix("陈：") != expected_fields
        ):
            raise ValueError(
                f"expert template confirmations are incomplete for {case_id}"
            )
        for pseudonym, role in (
            ("yu-nutritionist", "nutritionist"),
            ("chen-food-data-admin", "food_composition_data_steward"),
        ):
            review: dict[str, Any] = {
                "case_id": case_id,
                "role": role,
                "pseudonym": pseudonym,
                "rubric_version": "phase02-rubric.v1",
                "dataset_hash": dataset_hash,
                "code_eval_hash": code_eval_hash,
                "confirmations": {name: True for name in REQUIRED_CONFIRMATIONS},
            }
            if case_id in MEDIUM_CASES:
                match = re.fullmatch(r"于=(\d)；陈=(\d)", medium_text)
                if match is None:
                    raise ValueError(
                        f"expert template medium scores are ambiguous for {case_id}"
                    )
                score = int(match.group(1 if role == "nutritionist" else 2))
                if not 1 <= score <= 5:
                    raise ValueError(
                        f"expert template medium score is out of range for {case_id}"
                    )
                review["medium_human_score"] = score
            reviews.append(review)
    _write(
        output,
        {
            "schema_version": "expert-signoff.v1",
            "rubric_version": "phase02-rubric.v1",
            "dataset_hash": dataset_hash,
            "code_eval_hash": code_eval_hash,
            "reviewers": [
                {"pseudonym": "yu-nutritionist", "role": "nutritionist"},
                {
                    "pseudonym": "chen-food-data-admin",
                    "role": "food_composition_data_steward",
                },
            ],
            "reviews": reviews,
            "judge_scores": [
                {
                    "case_id": case_id,
                    "rubric_version": "phase02-rubric.v1",
                    "dataset_hash": dataset_hash,
                    "code_eval_hash": code_eval_hash,
                    "score": judge_scores[case_id],
                }
                for case_id in sorted(MEDIUM_CASES)
            ],
        },
    )


def _judge_score(value: Any) -> int:
    if not isinstance(value, str):
        raise OutputParseError("judge_score")
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as error:
        raise OutputParseError("judge_score") from error
    score = payload.get("score") if isinstance(payload, dict) else None
    if not isinstance(score, int) or not 1 <= score <= 5:
        raise OutputParseError("judge_score")
    return score


def _failure_category(output: str) -> str:
    normalized = output.lower()
    if any(
        marker in normalized
        for marker in ("econn", "enotfound", "timeout", "network", "socket", "dns")
    ):
        return "network_failure"
    if normalized:
        return "product_failure"
    return "unclassified_failure"


def _failure_stage(output: str) -> str:
    normalized = output.lower()
    if any(
        marker in normalized
        for marker in ("enotfound", "getaddrinfo", "nodename", "dns")
    ):
        return "dns"
    if any(marker in normalized for marker in ("certificate", "tls", "ssl")):
        return "tls"
    if re.search(r"\b(?:401|403|404|408|429|5\d\d)\b", normalized):
        return "http"
    if any(
        marker in normalized for marker in ("econn", "timeout", "network", "socket")
    ):
        return "transport"
    return "unknown"


def _decimal(value: Decimal | None) -> Decimal:
    if value is None or value < 0:
        raise ValueError("price snapshot value is required and non-negative")
    return value


def _usage_int(value: Any, default: int | None = None) -> int:
    if value is None and default is not None:
        return default
    if isinstance(value, int) and value >= 0:
        return value
    raise OutputParseError("usage")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write(path: Path, document: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    raise SystemExit(main())
