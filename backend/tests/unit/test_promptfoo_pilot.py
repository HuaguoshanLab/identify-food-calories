from __future__ import annotations

import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from evals.run_promptfoo_pilot import (  # noqa: E402
    MAX_CALLS,
    _case_ids,
    _failure_category,
    _validate_config,
)
from evals.run_promptfoo_release import (  # noqa: E402
    MAX_CALLS as RELEASE_MAX_CALLS,
    OutputParseError,
    _call_evidence,
    _failure_stage,
    _judge_prompt_contract,
    _judge_response_format,
    _judge_score,
    _judge_thinking,
    _materialize_signoff,
    _result_row,
    _validate_config as validate_release_config,
)


PILOT_CONFIG = Path("evals/promptfoo-pilot-phase2.yaml")


def test_pilot_config_is_fixed_to_eight_serial_non_release_calls() -> None:
    payload = PILOT_CONFIG.read_bytes()

    _validate_config(PILOT_CONFIG, payload, _case_ids(PILOT_CONFIG))

    assert len(_case_ids(PILOT_CONFIG)) == MAX_CALLS


def test_pilot_failure_accounting_keeps_network_and_product_distinct() -> None:
    assert (
        _failure_category(result_output="connect ECONNRESET", returncode=1)
        == "network_failure"
    )
    assert (
        _failure_category(result_output="request rejected", returncode=1)
        == "product_failure"
    )
    assert _failure_category(result_output="", returncode=1) == "unclassified_failure"


def test_release_contract_is_fixed_and_materializes_only_explicit_expert_fields(
    tmp_path: Path,
) -> None:
    config = Path("evals/promptfooconfig.yaml")
    validate_release_config(config.read_bytes())
    output = tmp_path / "expert-signoff.json"

    _materialize_signoff(
        template=Path("evals/expert-signoff-phase2.template.md"),
        output=output,
        dataset_hash="a" * 64,
        code_eval_hash="b" * 64,
        judge_scores={f"phase02-{number:03d}": 5 for number in range(6, 11)},
    )

    import json

    document = json.loads(output.read_text(encoding="utf-8"))
    assert RELEASE_MAX_CALLS == 36
    assert len(document["reviews"]) == 48
    assert {item["case_id"] for item in document["judge_scores"]} == {
        f"phase02-{number:03d}" for number in range(6, 11)
    }
    medium_scores = {
        (item["case_id"], item["pseudonym"]): item["medium_human_score"]
        for item in document["reviews"]
        if item["case_id"] in {"phase02-007", "phase02-009"}
    }
    assert medium_scores == {
        ("phase02-007", "yu-nutritionist"): 4,
        ("phase02-007", "chen-food-data-admin"): 5,
        ("phase02-009", "yu-nutritionist"): 5,
        ("phase02-009", "chen-food-data-admin"): 4,
    }


def test_release_prompt_uses_a_new_strict_json_contract() -> None:
    version, prompt = _judge_prompt_contract(
        Path("evals/promptfooconfig.yaml").read_bytes()
    )

    assert version == "phase02-judge-json-thinking-disabled.v4"
    assert '精确为 {"score": <1-5 的整数>}' in prompt
    assert "额外键" in prompt
    assert _judge_response_format(Path("evals/promptfooconfig.yaml").read_bytes()) == {
        "type": "json_object"
    }
    assert _judge_thinking(Path("evals/promptfooconfig.yaml").read_bytes()) == {
        "type": "disabled"
    }


def test_release_json_mode_is_transmitted_by_local_promptfoo_openai_provider() -> None:
    package = BACKEND_ROOT.parent / "frontend/node_modules/promptfoo/package.json"
    provider_source = next(
        (BACKEND_ROOT.parent / "frontend/node_modules/promptfoo/dist/src").glob(
            "providers-*.js"
        )
    )

    assert json.loads(package.read_text(encoding="utf-8"))["version"] == "0.122.0"
    source = provider_source.read_text(encoding="utf-8")
    assert (
        "config.response_format ? { response_format: maybeLoadResponseFormatFromExternalFile"
        in source
    )
    assert "...responseFormat," in source
    assert "...config.passthrough || {}" in source


@pytest.mark.parametrize(
    "value",
    [
        '{"score": 5, "reason": "synthetic"}',
        '{"score": true}',
        '{"score": "5"}',
        '{"score": 5.0}',
        "not-json",
    ],
)
def test_release_judge_score_requires_exact_non_boolean_integer_object(
    value: object,
) -> None:
    with pytest.raises(OutputParseError, match="judge_score"):
        _judge_score(value)

    assert _judge_score('{"score": 5}') == 5
    assert _judge_score({"score": 4}) == 4


def test_release_failure_stage_is_whitelisted_without_retaining_stderr() -> None:
    assert _failure_stage("getaddrinfo ENOTFOUND api.deepseek.com") == "dns"
    assert _failure_stage("certificate verify failed") == "tls"
    assert _failure_stage("HTTP 401") == "http"
    assert _failure_stage("socket timeout") == "transport"
    assert _failure_stage("unexpected") == "unknown"


def _safe_row(case_id: str = "phase02-006") -> dict[str, object]:
    return {
        "vars": {"case_id": case_id, "text": "synthetic fixture only"},
        "response": {
            "output": '{"score": 5}',
            "tokenUsage": {"prompt": 1, "completion": 1, "total": 2},
        },
    }


def test_release_reader_accepts_promptfoo_0122_nested_export_and_flat_compat_shape() -> (
    None
):
    row = _safe_row()

    assert _result_row({"results": {"results": [row]}}, "phase02-006") is row
    assert _result_row({"results": [row]}, "phase02-006") is row


def test_release_reader_rejects_non_target_case_instead_of_scoring_filter_range_blindly() -> (
    None
):
    with pytest.raises(OutputParseError, match="target_case"):
        _result_row({"results": {"results": [_safe_row("phase02-007")]}}, "phase02-006")


def test_release_parse_failure_persists_structure_only_without_sensitive_keys(
    tmp_path: Path,
) -> None:
    raw_export = tmp_path / "export.json"
    row = _safe_row()
    del row["response"]["tokenUsage"]  # type: ignore[index]
    raw_export.write_text(
        json.dumps(
            {
                "results": {"results": [row], "prompt": "do-not-store"},
                "config": {"apiKey": "do-not-store"},
            }
        ),
        encoding="utf-8",
    )

    evidence = _call_evidence(
        "phase02-006",
        1,
        subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
        raw_export,
        Decimal("1"),
        Decimal("1"),
    )

    assert evidence.status == "failed"
    assert evidence.parse_stage == "usage"
    assert evidence.output_shape is not None

    shape = evidence.output_shape
    rendered = json.dumps(shape)
    assert shape["results_type"] == "object"
    assert shape["nested_results_length"] == 1
    assert "do-not-store" not in rendered
    assert all(
        sensitive not in rendered
        for sensitive in ("prompt", "output", "value", "response", "vars")
    )


def test_release_judge_parse_failure_keeps_usage_accounting_without_output(
    tmp_path: Path,
) -> None:
    raw_export = tmp_path / "export.json"
    row = _safe_row()
    row["response"]["output"] = "synthetic-invalid-score"  # type: ignore[index]
    raw_export.write_text(json.dumps({"results": {"results": [row]}}), encoding="utf-8")

    evidence = _call_evidence(
        "phase02-006",
        1,
        subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
        raw_export,
        Decimal("1"),
        Decimal("1"),
    )

    assert evidence.status == "failed"
    assert evidence.parse_stage == "judge_score"
    assert (
        evidence.prompt_tokens,
        evidence.completion_tokens,
        evidence.total_tokens,
    ) == (
        1,
        1,
        2,
    )
    assert evidence.cost_usd == "0.000002"
    assert evidence.cost_cny_at_ceiling == "0.000016"
    assert "synthetic-invalid-score" not in json.dumps(evidence.output_shape)
