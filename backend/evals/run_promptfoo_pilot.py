"""Run the bounded, non-release Promptfoo pilot without exposing prompts or secrets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from app.core.config import Settings


MAX_CALLS = 8
MAX_OUTPUT_TOKENS = 32
REQUEST_OVERHEAD_TOKEN_CAP = 1024
BUDGET_CNY = Decimal("3")
# The PBOC USD/CNY central parity was about 7.04 in Dec 2025; 8.00 is a fixed
# conservative ceiling used solely to make the pilot preflight fail closed.
FX_CNY_PER_USD_CEILING = Decimal("8")


@dataclass(frozen=True)
class CallEvidence:
    case_id: str
    status: str
    failure_category: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    cost_usd: str | None
    cost_cny_at_ceiling: str | None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("evals/promptfoo-pilot-phase2.yaml"))
    parser.add_argument("--dataset", type=Path, default=Path("evals/phase02-cases.jsonl"))
    parser.add_argument("--code-eval", type=Path, default=Path("evals/phase2-code-eval.json"))
    parser.add_argument("--output", type=Path, default=Path("evals/promptfoo-pilot-phase2.json"))
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()

    settings = Settings()
    _validate_settings(settings)
    config_bytes = args.config.read_bytes()
    config_hash = _sha256(config_bytes)
    dataset_hash = _sha256(args.dataset.read_bytes())
    code_eval_hash = _sha256(args.code_eval.read_bytes())
    call_ids = _case_ids(args.config)
    _validate_config(args.config, config_bytes, call_ids)

    input_cap = len(config_bytes) + REQUEST_OVERHEAD_TOKEN_CAP
    input_price = _decimal(settings.deepseek_input_usd_per_m)
    output_price = _decimal(settings.deepseek_output_usd_per_m)
    maximum_per_call_usd = (
        Decimal(input_cap) * input_price + Decimal(MAX_OUTPUT_TOKENS) * output_price
    ) / Decimal("1000000")
    maximum_total_cny = maximum_per_call_usd * MAX_CALLS * FX_CNY_PER_USD_CEILING

    common = {
        "schema_version": "phase2-promptfoo-pilot-v1",
        "release_eligible": False,
        "model": settings.deepseek_model,
        "calls_authorized": MAX_CALLS,
        "max_concurrency": 1,
        "cache": "disabled",
        "max_retries": 0,
        "dataset_hash": dataset_hash,
        "code_eval_hash": code_eval_hash,
        "config_hash": config_hash,
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
            {**common, "status": "blocked_budget_preflight", "calls_attempted": 0, "calls_completed": 0, "calls": []},
        )
        return 2
    if args.preflight_only:
        _write(
            args.output,
            {**common, "status": "preflight_passed", "calls_attempted": 0, "calls_completed": 0, "calls": []},
        )
        return 0

    calls: list[CallEvidence] = []
    spent_cny = Decimal("0")
    with tempfile.TemporaryDirectory(prefix="phase2-promptfoo-pilot-") as directory:
        temp_dir = Path(directory)
        for index, case_id in enumerate(call_ids):
            if spent_cny + maximum_per_call_usd * FX_CNY_PER_USD_CEILING > BUDGET_CNY:
                calls.append(CallEvidence(case_id, "blocked", "budget", None, None, None, None, None))
                break
            raw_output = temp_dir / f"call-{index}.json"
            result = subprocess.run(
                [
                    "../frontend/node_modules/.bin/promptfoo",
                    "eval",
                    "-c",
                    str(args.config),
                    "--env-file",
                    ".env",
                    "--filter-range",
                    f"{index}:{index + 1}",
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
                    "CI": "true",
                    "PROMPTFOO_DISABLE_UPDATE": "true",
                    "NO_COLOR": "1",
                },
                capture_output=True,
                text=True,
                check=False,
            )
            evidence = _call_evidence(case_id, result, raw_output, input_price, output_price)
            calls.append(evidence)
            if evidence.cost_cny_at_ceiling is not None:
                spent_cny += Decimal(evidence.cost_cny_at_ceiling)
            if spent_cny > BUDGET_CNY or evidence.status != "completed":
                break

    status = "completed" if len(calls) == MAX_CALLS and all(call.status == "completed" for call in calls) else "stopped"
    cost_known = all(call.cost_cny_at_ceiling is not None for call in calls)
    _write(
        args.output,
        {
            **common,
            "status": status,
            "calls_attempted": len(calls),
            "calls_completed": sum(call.status == "completed" for call in calls),
            "actual_cost_cny_at_ceiling": str(spent_cny) if cost_known else None,
            "cost_accounting": "usage_accounted" if cost_known else "unknown_after_failed_call",
            "calls": [asdict(call) for call in calls],
            "generated_at": datetime.now(UTC).isoformat(),
        },
    )
    return 0 if status == "completed" else 1


def _validate_settings(settings: Settings) -> None:
    if settings.deepseek_api_key is None or not settings.deepseek_api_key.get_secret_value().strip():
        raise ValueError("DEEPSEEK_API_KEY is required")
    if settings.deepseek_model != "deepseek-v4-flash":
        raise ValueError("pilot requires pinned deepseek-v4-flash")
    if not settings.deepseek_price_snapshot_version:
        raise ValueError("DEEPSEEK_PRICE_SNAPSHOT_VERSION is required")
    _decimal(settings.deepseek_input_usd_per_m)
    _decimal(settings.deepseek_output_usd_per_m)


def _validate_config(path: Path, config_bytes: bytes, call_ids: list[str]) -> None:
    text = config_bytes.decode("utf-8")
    required = ("non_release: true", "maxRetries: 0", "max_tokens: 32", "maxConcurrency: 1", "repeat: 1")
    if any(value not in text for value in required):
        raise ValueError("pilot config is missing a hard safety setting")
    if len(call_ids) != MAX_CALLS or len(set(call_ids)) != MAX_CALLS:
        raise ValueError("pilot config must have exactly eight distinct cases")
    if "openai:chat:deepseek-v4-flash" not in text:
        raise ValueError("pilot config model changed")


def _case_ids(path: Path) -> list[str]:
    import re

    return re.findall(r"case_id:\s*(phase02-\d+)", path.read_text(encoding="utf-8"))


def _call_evidence(
    case_id: str,
    result: subprocess.CompletedProcess[str],
    raw_output: Path,
    input_price: Decimal,
    output_price: Decimal,
) -> CallEvidence:
    if result.returncode != 0 or not raw_output.exists():
        return CallEvidence(
            case_id,
            "failed",
            _failure_category(result_output=result.stdout + result.stderr, returncode=result.returncode),
            None,
            None,
            None,
            None,
            None,
        )
    try:
        document = json.loads(raw_output.read_text(encoding="utf-8"))
        row = document["results"][0]
        response = row.get("response") or row.get("providerResponse") or {}
        usage = response.get("tokenUsage") or row.get("tokenUsage") or {}
        prompt_tokens = _int(usage.get("prompt"))
        completion_tokens = _int(usage.get("completion"))
        total_tokens = _int(usage.get("total"), prompt_tokens + completion_tokens)
        cost_usd = (Decimal(prompt_tokens) * input_price + Decimal(completion_tokens) * output_price) / Decimal("1000000")
        cost_cny = cost_usd * FX_CNY_PER_USD_CEILING
    except (KeyError, TypeError, ValueError, InvalidOperation, json.JSONDecodeError):
        return CallEvidence(case_id, "failed", "product_failure", None, None, None, None, None)
    return CallEvidence(
        case_id,
        "completed",
        None,
        prompt_tokens,
        completion_tokens,
        total_tokens,
        str(cost_usd),
        str(cost_cny),
    )


def _decimal(value: Decimal | None) -> Decimal:
    if value is None or value < 0:
        raise ValueError("price snapshot value is required and non-negative")
    return value


def _int(value: Any, default: int | None = None) -> int:
    if value is None and default is not None:
        return default
    if isinstance(value, int) and value >= 0:
        return value
    raise ValueError("invalid usage value")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _failure_category(*, result_output: str, returncode: int) -> str:
    del returncode
    normalized = result_output.lower()
    network_markers = ("econn", "enotfound", "timeout", "network", "socket", "dns")
    if any(marker in normalized for marker in network_markers):
        return "network_failure"
    if normalized:
        return "product_failure"
    return "unclassified_failure"


def _write(path: Path, document: dict[str, Any]) -> None:
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
