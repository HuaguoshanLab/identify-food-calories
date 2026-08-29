from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from evals.run_promptfoo_pilot import (  # noqa: E402
    MAX_CALLS,
    _case_ids,
    _failure_category,
    _validate_config,
)


PILOT_CONFIG = Path("evals/promptfoo-pilot-phase2.yaml")


def test_pilot_config_is_fixed_to_eight_serial_non_release_calls() -> None:
    payload = PILOT_CONFIG.read_bytes()

    _validate_config(PILOT_CONFIG, payload, _case_ids(PILOT_CONFIG))

    assert len(_case_ids(PILOT_CONFIG)) == MAX_CALLS


def test_pilot_failure_accounting_keeps_network_and_product_distinct() -> None:
    assert _failure_category(result_output="connect ECONNRESET", returncode=1) == "network_failure"
    assert _failure_category(result_output="request rejected", returncode=1) == "product_failure"
    assert _failure_category(result_output="", returncode=1) == "unclassified_failure"
